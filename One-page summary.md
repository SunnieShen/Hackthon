Theme: Smarter Investment Decision ——**AI-Driven Intelligent Investment & Trading Innovation**

Aim: We focus on leveraging artificial intelligence to help young investors overcome knowledge gaps and experience deficiencies, enabling more rational investment decisions through intelligent analysis + educational guidance.

###  **Problem Identification: The Real Struggles of Young Investors**

##### **Core Pain Points: Information Overload & Decision Paralysis**
Young investors (18-35) are paying **painful tuition fees** due to lack of systematic knowledge:

- **86%** of young investors lost over 20% during the 2023 bear market - due to **blind following + lack of risk awareness**  
  *(Source: Shanghai Jiao Tong University "Youth Investment Behavior Research Report")*

- **72%** admit "**don't know when to buy or sell**" - leading to **decision anxiety + emotional trading**  
  *(Source: Ant Fortune "2024 China Youth Investment Survey")*

- **Single-day losses exceeding $1.4M** - A financial influencer's wrong prediction triggered collective panic selling among followers  
  *(Source: Securities Times, March 2024)*

> **Core Issue**: Information overload but knowledge deficiency, tools fragmentation but lack of integration, experience shortage but no guidance

## Project Overview
This is a stock investment analysis web platform developed based on the Flask framework, integrating real-time market data acquisition, technical indicator analysis, investment portfolio diagnostics, and AI intelligent analysis. The platform uses the yfinance library to fetch data from Yahoo Finance, providing investors with comprehensive stock market analysis tools to help them make more informed investment decisions.

## Four Core Feature Pages

### 1. Watchlist
- **Core Function**: Personalized stock tracking management
- **Main Features**:
  - Add/Remove custom tracked stocks
  - Real-time price display and percentage change monitoring
  - Technical indicator calculations (SMA, RSI, MACD, Bollinger Bands)
  - Data persistence storage
- **Technical Implementation**: Local JSON file storage, RESTful API interfaces

### 2. Hot Stocks
- **Core Function**: Real-time quotes display for mainstream tech stocks
- **Coverage**: 10 high-attention stocks including AAPL, MSFT, NVDA, AMZN
- **Data Dimensions**:
  - Real-time prices and trading volume
  - Intraday high/low prices
  - 52-week price range
  - Complete technical indicator analysis
- **Value Proposition**: Quickly grasp the performance of market leading stocks

### 3. Market Indices
- **Core Function**: Monitoring of global major indices and sector ETFs
- **Index Categories**:
  - **Global Indices**: S&P 500, Dow Jones, Nasdaq, FTSE 100, etc.
  - **Sector ETFs**: 9 major sectors including Technology, Financials, Energy, Healthcare
- **Special Features**:
  - Index constituent stocks display
  - Cross-market linkage analysis
  - Sector rotation tracking
- **Application Value**: Insights into macro market trends and sector performance

### 4. Portfolio Analysis
- **Core Function**: Intelligent portfolio diagnostics and optimization suggestions
- **Analysis Dimensions**:
  - **Diversification Assessment**: HHI index calculation for diversity scoring
  - **Risk Analysis**: Single stock concentration, sector concentration, valuation levels
  - **Fundamental Diagnostics**: Weighted average PE, sector distribution
- **AI Enhancement**:
  - Rule engine-based automatic risk assessment
  - Personalized rebalancing suggestions
  - DeepSeek AI integration for deep analysis
- **Core Value**: Scientific quantification of portfolio health

## Competitive Advantages: Comparison with Traditional Tools

| Feature Dimension | Our Platform | Traditional Broker Apps | Professional Financial Websites | Professional Terminals |
|:---|:---|:---|:---|:---|
| **Core Positioning** | Intelligent Decision Support System | Trade Execution Tool | Information Aggregation Portal | Institutional-grade Data Terminal |
| **Function Focus** | Data analysis, portfolio diagnostics, AI insights | Order execution, basic quotes | News, announcements, community discussions | Comprehensive market depth data, historical backtesting |
| **Integration Level** | ⭐⭐⭐⭐⭐<br>Highly Integrated | ⭐⭐<br>Fragmented Functions | ⭐⭐<br>Information Fragmentation | ⭐⭐⭐⭐<br>Comprehensive but complex |
| **Analysis Depth** | ⭐⭐⭐⭐<br>Automatic technical indicators + Portfolio risk diagnostics | ⭐<br>Only basic indicators | ⭐⭐<br>Provides data but lacks deep analysis | ⭐⭐⭐⭐⭐<br>Extreme depth, supports complex modeling |
| **Intelligence** | ⭐⭐⭐⭐<br>Rule Engine + AI Hybrid Intelligence | ⭐<br>Almost no intelligent analysis | ❌ | ⭐⭐⭐<br>Powerful, but requires user expertise |
| **User Experience** | ⭐⭐⭐⭐<br>Simple and intuitive | ⭐⭐⭐<br>Smooth, but trade-oriented | ⭐⭐<br>Cluttered pages, many ads | ⭐<br>Extremely complex, steep learning curve |
| **Cost** | 💲 (Potentially free or low cost) | 💲 (Usually free) | 💲 (Usually free) | 💲💲💲💲💲 (Extremely expensive) |
| **Target Users** | Retail investors seeking professional analysis | Average traders | Information browsers | Institutional analysts, professional traders |

### Key Limitations and Specific Improvement Plans

| Category | Specific Issues | Concrete Solutions |
|----------|-----------------|-------------------|
| **Data Issues** | Only fetches data from Yahoo Finance, often missing China A-share data | 1. Add Tencent Finance as additional data source<br>2. Integrate Sina Finance API<br>3. Implement automatic data completion mechanism |
| **Performance Issues** | Recalculates all indicators on every refresh, slow loading | 1. Install Redis to cache price data<br>2. Pre-calculate technical indicators and cache them<br>3. Replace JSON files with MySQL database |
| **Functionality Gaps** | Cannot record purchase prices and quantities, no actual P&L visibility | 1. Add position cost input fields<br>2. Implement profit/loss calculation functionality<br>3. Add returns trend charts |
| **User Experience** | All users see the same watchlist, no personalization | 1. Add user registration and login functionality<br>2. Implement separate data storage for each user<br>3. Support customizable dashboard layout |


