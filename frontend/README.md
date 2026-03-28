# CoinTrader Frontend

React + TypeScript frontend for the automated cryptocurrency trading bot.

## Features

- Real-time trading dashboard
- Chart visualization with market data
- Strategy management
- AI-powered trading advisor
- Order management and portfolio tracking
- Backtesting tools
- User authentication and settings

## Tech Stack

- **React 18.3** - UI framework
- **TypeScript 5.6** - Type-safe development
- **Vite 5.4** - Build tool and dev server
- **Tailwind CSS 3.4** - Styling
- **React Router 6.26** - Client-side routing
- **Zustand 4.5** - State management
- **Axios 1.7** - HTTP client
- **Lucide React 0.445** - Icon library
- **Lightweight Charts 4.2** - Chart visualization

## Getting Started

### Prerequisites

- Node.js 20+
- npm or yarn

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

### Building

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

### Linting

```bash
npm run lint
```

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client and services
│   ├── components/       # Reusable components
│   │   └── common/      # Common layout and UI components
│   ├── pages/           # Page components
│   ├── stores/          # Zustand store definitions
│   ├── App.tsx          # Main app component with routing
│   ├── main.tsx         # Entry point
│   └── index.css        # Global styles
├── index.html           # HTML template
├── package.json         # Dependencies and scripts
├── tsconfig.json        # TypeScript configuration
├── vite.config.ts       # Vite configuration
├── tailwind.config.js   # Tailwind CSS configuration
└── Dockerfile           # Docker configuration
```

## Pages

- `/` - Dashboard
- `/login` - Login page
- `/chart/:symbol` - Cryptocurrency chart
- `/strategies` - Trading strategies
- `/ai-advisor` - AI trading advisor
- `/orders` - Active and past orders
- `/portfolio` - Portfolio overview
- `/backtest` - Backtesting tools
- `/settings` - Application settings

## Authentication

The app uses JWT token-based authentication. The token is stored in localStorage and automatically included in API requests via an Axios interceptor.

Demo credentials:
- Email: `test@example.com`
- Password: `password123`

## Docker

Build and run with Docker:

```bash
docker build -t coin-trader-frontend .
docker run -p 3000:3000 coin-trader-frontend
```

## API Integration

The frontend proxies requests to the backend API at `http://backend:8000` (configured in `vite.config.ts`).

Key API endpoints:
- `POST /api/v1/auth/login` - User authentication
- Other endpoints documented in backend API

## Development Notes

- All API requests use the Axios client from `src/api/client.ts`
- Authentication state is managed with Zustand in `src/stores/authStore.ts`
- Dark theme using Tailwind CSS with custom component classes in `src/index.css`
- UI uses Korean labels and supports internationalization
