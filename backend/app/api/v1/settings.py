from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.exchange_account import ExchangeAccount
from app.models.balance import Balance
from app.schemas.exchange import ExchangeAccountCreate, ExchangeAccountResponse, BalanceResponse, BalanceItem
from app.core.encryption import encrypt_api_key, decrypt_api_key
from app.exchange.ccxt_adapter import CcxtAdapter
from app.config import ALLOWED_EXCHANGE_IDS

router = APIRouter(prefix="/exchange", tags=["exchange"])


@router.get("/accounts", response_model=list[ExchangeAccountResponse])
async def list_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """연결된 거래소 계정 목록"""
    result = await db.execute(
        select(ExchangeAccount).where(ExchangeAccount.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/accounts", response_model=ExchangeAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: ExchangeAccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """거래소 API Key 등록"""
    if data.exchange_id not in ALLOWED_EXCHANGE_IDS:
        raise HTTPException(status_code=400, detail="허용되지 않은 거래소입니다.")

    # 연결 테스트
    try:
        adapter = CcxtAdapter(
            exchange_id=data.exchange_id,
            api_key=data.api_key,
            api_secret=data.api_secret,
            testnet=data.is_testnet,
        )
        await adapter.get_balance()
        await adapter.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"거래소 연결 실패: {str(e)}")

    # API Key 암호화 저장
    account = ExchangeAccount(
        user_id=current_user.id,
        exchange_id=data.exchange_id,
        api_key_encrypted=encrypt_api_key(data.api_key),
        api_secret_encrypted=encrypt_api_key(data.api_secret),
        is_testnet=data.is_testnet,
        is_active=True,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """거래소 계정 삭제"""
    result = await db.execute(
        select(ExchangeAccount).where(
            ExchangeAccount.id == account_id,
            ExchangeAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")

    await db.delete(account)
    await db.commit()


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 잔고 조회 (활성 계정 사용)"""
    result = await db.execute(
        select(ExchangeAccount).where(
            ExchangeAccount.user_id == current_user.id,
            ExchangeAccount.is_active == True,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="연결된 거래소 계정이 없습니다.")

    try:
        api_key = decrypt_api_key(account.api_key_encrypted)
        api_secret = decrypt_api_key(account.api_secret_encrypted)

        adapter = CcxtAdapter(
            exchange_id=account.exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            testnet=account.is_testnet,
        )
        raw_balance = await adapter.get_balance()
        await adapter.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"잔고 조회 실패: {str(e)}")

    balances = [
        BalanceItem(
            symbol=symbol,
            available=amounts["available"],
            locked=amounts["locked"],
            total=amounts["total"],
        )
        for symbol, amounts in raw_balance.items()
    ]

    return BalanceResponse(
        exchange_id=account.exchange_id,
        is_testnet=account.is_testnet,
        balances=balances,
        synced_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/balance/sync", response_model=BalanceResponse)
async def sync_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """잔고 강제 동기화 - DB에 저장"""
    result = await db.execute(
        select(ExchangeAccount).where(
            ExchangeAccount.user_id == current_user.id,
            ExchangeAccount.is_active == True,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="연결된 거래소 계정이 없습니다.")

    try:
        api_key = decrypt_api_key(account.api_key_encrypted)
        api_secret = decrypt_api_key(account.api_secret_encrypted)

        adapter = CcxtAdapter(
            exchange_id=account.exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            testnet=account.is_testnet,
        )
        raw_balance = await adapter.get_balance()
        await adapter.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"잔고 동기화 실패: {str(e)}")

    now = datetime.now(timezone.utc)
    balances = []

    for symbol, amounts in raw_balance.items():
        # Upsert balance record
        res = await db.execute(
            select(Balance).where(
                Balance.user_id == current_user.id,
                Balance.exchange_id == account.exchange_id,
                Balance.symbol == symbol,
            )
        )
        bal = res.scalar_one_or_none()

        if bal:
            bal.available = amounts["available"]
            bal.locked = amounts["locked"]
            bal.synced_at = now
        else:
            bal = Balance(
                user_id=current_user.id,
                exchange_id=account.exchange_id,
                symbol=symbol,
                available=amounts["available"],
                locked=amounts["locked"],
                synced_at=now,
            )
            db.add(bal)

        balances.append(BalanceItem(
            symbol=symbol,
            available=amounts["available"],
            locked=amounts["locked"],
            total=amounts["total"],
        ))

    await db.commit()

    return BalanceResponse(
        exchange_id=account.exchange_id,
        is_testnet=account.is_testnet,
        balances=balances,
        synced_at=now.isoformat(),
    )
