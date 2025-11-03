graph TD
    subgraph "User Interface"
        A[User] --> B[Chat UI<br>templates/index.html]
        B --> E
        U[Human Reviewer] --> T[Review UI<br>templates/revisao.html]
        T --> V
    end

    subgraph "API Layer (FastAPI)"
        C[FastAPI App<br>resync/main.py]
        E[WebSocket API<br>resync/api/chat.py]
        V[Audit API<br>resync/api/audit.py]
        C --> E
        C --> V
    end

    subgraph "Core Logic"
        G[AgentManager<br>resync/core/agent_manager.py]
        K[Knowledge Graph<br>resync/core/knowledge_graph.py]
        M[IA Auditor<br>resync/core/ia_auditor.py]
        S[Scheduler (APScheduler)]
        E --> G
        V --> K
        G --> K
        G --> J
        M --> K
        M --> L
        S --> M
    end

    subgraph "AI / Data Layer"
        I[Agent Config<br>config/runtime.json]
        J[TWS Tools<br>resync/tool_definitions/tws_tools.py]
        L[LLM Service<br>resync/core/utils/llm.py]
        P[Vector Store<br>Mem0 AI + Qdrant]
        G --> I
        K --> P
    end

    subgraph "External Services"
        H[OptimizedTWSClient<br>resync/services/tws_service.py]
        N[HCL TWS Server]
        J --> H
        H --> N
    end

    %% --- Enhanced State Management ---
    style K fill:#fb9,stroke:#444,stroke-width:2px
    style M fill:#fb9,stroke:#444,stroke-width:2px
    style V fill:#fb9,stroke:#444,stroke-width:2px
    style N fill:#f66,stroke:#444,stroke-width:2px

    %% --- New Atomic Data Flow ---
    M -- "Check is_memory_flagged()" --> K
    M -- "Check is_memory_approved()" --> V
    V -- "status: pending" --> M
    V -- "status: approved/rejected" --> K
    M -- "Add FLAGGED_BY_IA" --> K
    M -- "Add audit record to Redis" --> V

    %% --- New Async Lock for TWS Client ---
    G -- "Async Lock" --> H

    %% --- New SSL Verification ---
    H -- "verify=settings.TWS_VERIFY_SSL" --> N

    %% --- New Audit Queue ---
    V -- "Redis-based Audit Queue" --> Aq[Redis Cluster]
    Aq -- "High-concurrency, atomic operations" --> V

    %% Styling
    style A fill:#c9f,stroke:#333,stroke-width:2px
    style U fill:#c9f,stroke:#333,stroke-width:2px
    style B fill:#bbf,stroke:#333,stroke-width:2px
    style T fill:#bbf,stroke:#333,stroke-width:2px
    style C fill:#9f9,stroke:#333,stroke-width:2px
    style E fill:#aef,stroke:#333,stroke-width:2px
    style V fill:#dcf,stroke:#333,stroke-width:2px
    style G fill:#ff6,stroke:#333,stroke-width:2px
    style K fill:#f96,stroke:#333,stroke-width:2px
    style M fill:#f96,stroke:#333,stroke-width:2px
    style S fill:#f96,stroke:#333,stroke-width:2px
    style I fill:#ddf,stroke:#333,stroke-width:2px
    style J fill:#ff6,stroke:#333,stroke-width:2px
    style L fill:#f69,stroke:#333,stroke-width:2px
    style P fill:#f69,stroke:#333,stroke-width:2px
    style H fill:#e96,stroke:#333,stroke-width:2px
    style N fill:#f66,stroke:#333,stroke-width:2px
    style Aq fill:#d6f,stroke:#333,stroke-width:2px



