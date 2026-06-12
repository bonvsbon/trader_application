You are Claude Code acting as a senior full-stack architect, trading system engineer, and risk-management engineer.

I want you to build a web application for trading that supports both manual trading and automated trading. The first target instrument is XAUUSD / Gold, but the architecture must support adding more symbols later such as stocks, indices, crypto, forex, or commodities.

Important instruction:
Do not start coding immediately. First, inspect the current project structure that I will provide in this folder. After reading the structure, propose an implementation plan and wait for my approval before making major changes.

========================
PROJECT GOAL
============

Build a trading web application that integrates with MetaTrader 5 and supports:

1. Manual trading
2. Auto trading on demo account
3. Auto trading on real account with mandatory manual approval in the first phase
4. Configurable future option for fully automated real trading, but it must be disabled by default
5. AI-assisted analysis for price, chart, news, volatility, risk/reward, and trade decision support
6. Interval-based workflow with visible countdown and execution status
7. Learning system that records trade mistakes, losing trades, user notes, research findings, and strategy improvements into markdown files

The system must be designed with safety first. The app must never place a real-money order unless the config explicitly allows it and the approval/risk rules pass.

========================
CORE REQUIREMENTS
=================

A. MetaTrader 5 Integration

Design the most stable architecture for MT5 integration.

Evaluate and recommend the best approach among:

* MT5 Expert Advisor Bridge
* Local HTTP/WebSocket bridge
* File-based JSON bridge
* Python MT5 package
* Hybrid approach

The system should support:

* Demo account
* Real account
* Account status sync
* Balance/equity/margin/free margin
* Symbol price feed from MT5
* Open positions
* Pending orders
* Trade history
* Order execution
* Order modification
* Order close
* MT5 connection heartbeat
* Bridge health status
* Error handling and retry logic

Important:
The preferred architecture should prioritize stability and prevention of missed opportunities, but also avoid unsafe duplicate orders.

Required safety features:

* Idempotency key for every trade request
* Duplicate order prevention
* Order state machine
* Execution log
* Bridge heartbeat
* Circuit breaker if MT5 connection is unstable
* Real account protection
* Manual approval required for real account in early phase
* Configurable emergency stop / kill switch

B. Trading Modes

Support these modes:

1. MANUAL_ONLY
   User manually opens trades from the web UI.

2. AUTO_DEMO
   System can auto-analyze and auto-place orders only on demo account.

3. AUTO_REAL_APPROVAL_REQUIRED
   System can analyze and generate real-account trade proposals, but user must confirm before the order is sent.

4. AUTO_REAL_FULL
   System can place real-account trades automatically only if enabled by explicit config. This mode must be disabled by default and protected by multiple warnings and risk checks.

C. First Strategy Preset

Start with the existing XAUUSD preset:

* Symbol: XAUUSD
* Primary concept: D40/D20
* TP: 2R
* Risk: 1%
* News filter required
* Avoid trading during high-impact news
* Real account requires manual confirmation in early phase

If strategy details are incomplete, create a Strategy Interface and implement this as a configurable preset placeholder first. Do not hardcode everything in random places.

D. Risk Management

Build a strong risk-management module.

Minimum rules:

* Block trading during high-impact news
* Block trading if spread is too high
* Block trading if volatility is abnormal
* Block trading if MT5 bridge is unhealthy
* Block trading if account margin is unsafe
* Block real-account trades unless approval rules pass
* Daily max loss
* Max trades per day
* Max open positions
* Max risk per trade
* Max total portfolio risk
* Cooldown after losing trade
* Kill switch
* Manual override with audit log

The Risk Manager must return a clear decision:

* ALLOW
* WARN
* BLOCK

It must also return human-readable reasons.

Example:
{
"decision": "BLOCK",
"reasons": [
"High-impact USD news within 30 minutes",
"Spread is above configured limit",
"Real account requires manual approval"
]
}

E. AI Analysis

The system must support AI analysis using multiple providers with failover.

Provider targets:

* Claude
* OpenAI/GPT
* Local LLM
* Future MCP tools

Build an AI Provider abstraction layer.

Required AI functions:

* Analyze chart context
* Analyze news
* Analyze volatility
* Analyze risk/reward
* Recommend entry / no-entry
* Explain trade setup
* Summarize current market condition
* Generate trade proposal
* Review losing trades
* Learn from past mistakes
* Read markdown memory/skill files
* Write updated learning notes into markdown files

Important:
AI must not be the only safety layer. Even if AI says BUY or SELL, the Risk Manager must validate before any order is placed.

F. News and Volatility

The first instrument is XAUUSD.

The system must collect or prepare integration for:

* Economic calendar
* High-impact USD news
* Gold-related news
* Volatility signal
* Market session information
* News risk score

Let the AI/MCP provider search and evaluate news when tools are available. If external APIs are not ready, create a provider interface and mock implementation first.

The UI must clearly show:

* Current news risk
* Upcoming high-impact events
* Whether trading is blocked by news
* AI summary of news impact
* Last news check time

G. Interval Workflow

The app must support configurable interval workflows.

The interval workflow should be able to run:

* Pull latest MT5 price
* Pull/sync chart data
* Pull/sync news
* Analyze with AI
* Check strategy signal
* Run risk checks
* Generate trade proposal
* Execute if mode allows
* Sync orders and positions from MT5
* Write logs
* Update countdown

UI must show:

* Whether the workflow is running or stopped
* Current workflow step
* Last run time
* Next run time
* Countdown in minutes and seconds
* Progress/status
* Errors if any
* Manual run button
* Start/stop button
* Configurable interval in seconds/minutes

Example UI status:
Running: Yes
Current step: AI Analysis
Last run: 2026-06-11 09:30:00
Next run: 2026-06-11 09:35:00
Countdown: 04:32

H. Web Application Pages

Create or plan these pages:

1. Dashboard

* Account summary
* MT5 connection status
* Current trading mode
* Risk status
* Latest AI summary
* Active positions
* Countdown workflow
* News risk

2. Watchlist

* XAUUSD first
* Add more symbols later
* Price
* Spread
* Trend
* Volatility
* AI bias
* Trading status

3. Realtime Chart

* Realtime chart per symbol
* Timeframe selector
* Price candles if available
* Indicators placeholder
* Strategy signal markers
* Trade entry/exit markers

4. Search Symbol / Stock Detail

* Search instrument
* View symbol detail
* Price
* Chart
* AI analysis
* Trade availability
* Risk status

5. AI Analysis

* News summary
* Chart summary
* Risk/reward
* Entry/no-entry recommendation
* Confidence level
* Risk warning
* Suggested SL/TP
* Explanation

6. Manual Order Ticket

* Symbol
* Buy/Sell
* Lot size
* SL
* TP
* Risk %
* Estimated loss
* Estimated reward
* Submit order
* Confirmation modal for real account

7. Auto Strategy Control

* Enable/disable strategy
* Select mode
* Configure preset
* Configure risk rules
* Configure interval
* Start/stop workflow
* Show last decision

8. Interval Countdown

* Running status
* Countdown
* Current step
* Next run
* Manual trigger

9. MT5 Account Status

* Account type
* Demo/real
* Balance
* Equity
* Margin
* Free margin
* Open positions
* Bridge heartbeat

10. Trade History

* Orders
* Positions
* Result
* R multiple
* Profit/loss
* Reason for entry
* Reason for exit
* AI analysis snapshot
* Risk decision snapshot

11. Risk Monitor

* News filter
* Spread filter
* Volatility filter
* Daily loss
* Max trades
* Margin condition
* Real-account guard
* Current block/warn/allow state

12. Logs

* System logs
* AI logs
* MT5 bridge logs
* Order execution logs
* Risk decision logs
* Error logs

13. Settings / Analysis Providers

Provide a dedicated **Settings** menu with an **Analysis Providers** page.
This page configures AI and MCP providers used to check data and produce
advisory analysis. It must remain separate from MT5 account/execution settings.

Provider types:

* Claude
* OpenAI/GPT
* Local LLM
* MCP server

MCP configuration must support:

* Display name
* Enabled/disabled state
* Transport: Streamable HTTP or SSE
* Server endpoint
* Authentication secret reference (never return or store a plaintext secret)
* Request timeout
* Priority and fallback order
* Capability assignments:
  * News search/check
  * Economic-calendar check
  * Chart/market analysis
  * Volatility/session analysis
  * Trade proposal explanation
  * Losing-trade review
* Connection test
* Tool/capability discovery
* Health state, latency, last check time, and last error

Provider routing requirements:

* Select a primary provider and ordered fallbacks per capability.
* Skip disabled or unhealthy providers.
* Record which provider/tool produced every analysis snapshot.
* Persist non-secret provider configuration and an audit log for every change.
* Treat MCP/tool output as untrusted advisory data and validate it before use.
* Apply timeouts, response-size limits, and allowlisted capabilities.
* Do not allow arbitrary local commands or arbitrary stdio server definitions
  from the web UI.
* AI/MCP providers must never call the MT5 bridge or place orders directly.
* Every resulting proposal must still pass the Risk Manager and `OrderService`.
* If a required live news/volatility capability has no healthy provider,
  real-account trading must remain blocked.

I. Learning and Memory System

The system must learn from mistakes but must not become unsafe.

Learning requirements:

* Record every trade decision
* Record every losing trade
* Record user feedback
* Record AI analysis snapshot
* Record risk decision snapshot
* Record what went wrong
* Record suggested improvement
* Store learnings as markdown files
* Keep files small and organized
* Do not store everything in one huge file

Suggested markdown structure:

* /memory/strategy/xauusd.md
* /memory/strategy/xauusd-loss-review.md
* /memory/news/gold-usd-news-notes.md
* /memory/risk/risk-rules.md
* /memory/user-rules/manual-overrides.md
* /memory/system/decision-journal.md
* /memory/skills/trading-skill.md
* /memory/skills/mt5-bridge-skill.md

The AI should read these markdown files before analysis and update them only when useful.

Do not let the AI directly rewrite critical risk rules without user approval.

J. Deployment Requirement

The web app should support flexible deployment:

* Local development
* Docker
* Server/VPS
* Future cloud deployment

Use environment variables for:

* MT5 bridge URL/path
* AI provider keys
* MCP provider endpoints and secret references
* Trading mode
* Risk config
* News provider config
* Database connection
* App port

K. Architecture Requirement

Before coding, propose architecture for:

* Frontend
* Backend
* Database
* MT5 Bridge
* AI Provider Layer
* MCP Client / Tool Provider Layer
* Risk Engine
* Strategy Engine
* Scheduler/Interval Worker
* Logging
* Markdown Memory System
* Deployment

Use clean separation of concerns.

Do not mix:

* UI logic
* trading execution logic
* risk rules
* AI prompts
* MT5 bridge code
* strategy code

L. Database / Persistence

Recommend suitable persistence.

At minimum, support storage for:

* Users/config
* AI/MCP provider registry and capability routing
* Symbols
* Price snapshots
* AI analysis
* Trade proposals
* Orders
* Positions
* Risk decisions
* Workflow runs
* Logs
* Learning metadata

If the project already has database conventions, follow the existing project structure.

M. Safety Rules

Hard rules:

1. Never place real account orders by default.
2. Real account orders require manual confirmation in Phase 1.
3. Every order must pass Risk Manager first.
4. Every order must have an audit log.
5. Every automated order must have strategy reason + AI reason + risk result.
6. If bridge status is unknown, block trading.
7. If account type is unknown, block trading.
8. If high-impact news is near, block trading.
9. If duplicate order is suspected, block trading.
10. If config is missing, block trading.

========================
PHASED IMPLEMENTATION
=====================

Phase 1: Foundation + Manual Trading + Demo Safety

Goal:
Build the foundation of the web app, MT5 connection design, manual order flow, dashboard, interval status, and risk manager.

Phase 1 deliverables:

* Read existing project structure
* Propose architecture
* Create config structure
* Create MT5 bridge abstraction
* Create mock/stub bridge if real bridge is not ready
* Create Risk Manager
* Create Manual Order Ticket
* Create Dashboard
* Create MT5 Account Status page
* Create Logs page
* Create Interval Countdown component
* Create basic workflow runner
* Store logs and decisions
* Real account order must require manual approval
* Auto real must be disabled

Phase 2: AI Analysis + News + Strategy Engine

Goal:
Add AI analysis, news/volatility assessment, XAUUSD strategy preset, and trade proposal system.

Phase 2 deliverables:

* AI provider abstraction
* Claude provider
* OpenAI provider placeholder
* Local LLM provider placeholder
* Settings / Analysis Providers page
* Persisted AI/MCP provider registry
* MCP Streamable HTTP/SSE client
* MCP connection test and tool discovery
* Capability routing and provider fallback
* Provider failover
* News provider abstraction
* News risk score
* XAUUSD AI Analysis page
* Strategy Engine interface
* XAUUSD D40/D20 TP2R risk 1% preset
* Trade proposal generation
* Risk/reward calculation
* AI explanation
* Approval flow before execution

Phase 3: Auto Workflow + Learning System + Production Hardening

Goal:
Enable automated demo workflow, real-account approval workflow, learning from losing trades, markdown memory, and deployment hardening.

Phase 3 deliverables:

* Full interval workflow
* Start/stop scheduler
* Countdown status
* Auto demo execution
* Real account approval queue
* Trade history with R multiple
* Losing trade review
* Markdown memory system
* Skill files
* Daily summary
* Error recovery
* Retry/circuit breaker
* Docker support
* Deployment docs
* Security and secret management
* Production readiness checklist

========================
WHAT I WANT YOU TO DO FIRST
===========================

Step 1:
Inspect the current folder and project structure.

Step 2:
Summarize what kind of project this is.

Step 3:
Tell me whether the existing structure is suitable or needs adjustment.

Step 4:
Propose the architecture and folder structure.

Step 5:
Propose the Phase 1 task list with exact files you will create or modify.

Step 6:
Wait for my approval before implementing.

Do not skip the planning step.
Do not start coding before explaining the plan.
Do not make unsafe trading assumptions.
Do not enable real auto trading by default.
