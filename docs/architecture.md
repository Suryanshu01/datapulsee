# DataPulse Architecture

## System Overview

```mermaid
graph LR
    User["User (Browser)"]

    subgraph Frontend["React Frontend (Vite, port 3000)"]
        Upload["UploadPanel"]
        Chat["ChatInterface"]
        Dict["SemanticLayer Editor"]
        Charts["Animated Charts"]
    end

    subgraph Backend["FastAPI Backend (port 8000)"]
        Routes["Routes: upload, query, semantic"]
        Pipeline["Query Pipeline"]
        Analyzer["Schema Analyzer"]
        SemEngine["Semantic Engine"]
        Cache["Query Cache"]
    end

    subgraph External["External Services"]
        Groq["Groq API (Llama 3.3 70B)"]
    end

    DuckDB["DuckDB (In-Memory)"]

    User --> Frontend
    Frontend --> Routes
    Routes --> Pipeline
    Routes --> Analyzer
    Routes --> SemEngine
    Pipeline --> Groq
    SemEngine --> Groq
    Pipeline --> DuckDB
    Analyzer --> DuckDB
    Pipeline --> Cache
```

## Query Pipeline (Two-Agent Pattern)

Inspired by [Azure SQL's Collaborating Agents](https://devblogs.microsoft.com/azure-sql/a-story-of-collaborating-agents-chatting-with-your-database-the-right-way/).

```mermaid
sequenceDiagram
    participant U as User
    participant R as /api/ask Route
    participant C as Cache
    participant A1 as Agent 1: Analyst
    participant A2 as Agent 2: SQL Writer
    participant DB as DuckDB
    participant A3 as Agent 3: Explainer

    U->>R: POST question + mode
    R->>C: Check cache
    alt Cache hit
        C-->>R: Cached response
        R-->>U: Return (cached=true)
    else Cache miss
        R->>A1: question + semantic layer + mode
        A1-->>R: intent, relevant_metrics, relevant_dimensions, plan
        alt Needs clarification
            R-->>U: clarification_question + options
        else Clear question
            R->>A2: plan + relevant schema only
            A2-->>R: DuckDB SQL
            R->>DB: Execute SQL
            alt SQL fails
                DB-->>R: Error
                R->>A2: Error + fix request
                A2-->>R: Fixed SQL
                R->>DB: Retry
            end
            DB-->>R: Results
            R->>A3: question + SQL + results + intent
            A3-->>R: explanation, insight_line, chart_config, kpis, follow_ups
            R->>C: Store in cache
            R-->>U: Full response
        end
    end
```

## Semantic Layer Structure

Mirrors [Snowflake Cortex Analyst's Semantic Model](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec).

```mermaid
classDiagram
    class SemanticLayer {
        +String data_summary
        +Metric[] metrics
        +Dimension[] dimensions
        +TimeDimension[] time_dimensions
    }

    class Metric {
        +String name
        +String description
        +String expr
        +String column
        +String data_type
        +String[] synonyms
    }

    class Dimension {
        +String name
        +String description
        +String column
        +String data_type
        +String[] sample_values
    }

    class TimeDimension {
        +String name
        +String description
        +String column
        +String data_type
        +String granularity
    }

    SemanticLayer --> Metric
    SemanticLayer --> Dimension
    SemanticLayer --> TimeDimension
```

## Visual-First Answer Hierarchy

Every assistant answer follows this layout (top to bottom):

1. **KPI Cards Row** — 2-4 animated counter cards with deltas
2. **Hero Chart** — Primary visualization (bar/line/donut/waterfall)
3. **Insight Line** — One bold sentence summarizing the key finding
4. **Explanation** — 3-5 sentences of plain-English context
5. **Data Table** — Collapsed by default, expandable
6. **Follow-up Chips** — 2-3 suggested next questions
7. **Transparency** — Collapsed "How was this answered?" with SQL, confidence, coverage

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| DuckDB over SQLite | Analytical queries (GROUP BY, window functions) run faster |
| Groq over OpenAI | Free tier with generous rate limits, fast inference |
| System fonts over Google Fonts | Instant load, native feel, no external requests |
| Light theme | Professional appearance, matches NatWest design language |
| Two-agent split | Agent 2 sees only relevant columns, reducing hallucination |
| Snowflake-format semantic layer | Matches judges' internal tooling (Cortex Analyst) |
| In-memory cache | Simple, no external dependency, good enough for demo |
| Recharts | React-native charts with built-in animation support |
