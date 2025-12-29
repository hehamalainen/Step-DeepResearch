"""Demo scenarios for testing the deep research agent."""

DEMO_SCENARIOS = [
    {
        "id": "planning-microservices",
        "name": "Microservices Migration",
        "description": "Plan a migration from monolith to microservices",
        "query": "Create a comprehensive migration plan for transitioning a Python Django monolith to microservices architecture. Include technology choices, data migration strategy, and rollout phases.",
        "category": "planning",
        "expected_tools": ["web_search", "web_browse", "todo", "file_write"],
    },
    {
        "id": "info-llm-training",
        "name": "LLM Training Techniques",
        "description": "Research modern LLM training approaches",
        "query": "What are the current state-of-the-art techniques for training large language models efficiently? Cover data preparation, distributed training, and fine-tuning methods.",
        "category": "information_seeking",
        "expected_tools": ["web_search", "web_browse", "reflect"],
    },
    {
        "id": "verify-climate",
        "name": "Climate Statistics Verification",
        "description": "Verify climate change claims with authoritative sources",
        "query": "Verify the claim: 'Global temperatures have risen by 1.1°C since pre-industrial times.' Find authoritative sources and cross-validate the data.",
        "category": "verification",
        "expected_tools": ["web_search", "web_browse", "cross_validate"],
    },
    {
        "id": "report-quantum",
        "name": "Quantum Computing Report",
        "description": "Generate a technical briefing on quantum computing",
        "query": "Write a technical brief on the current state of quantum computing, covering hardware approaches (superconducting, trapped ion, photonic), key players, and near-term applications.",
        "category": "reporting",
        "expected_tools": ["web_search", "web_browse", "todo", "file_write", "reflect"],
    },
    {
        "id": "authority-medical",
        "name": "Medical Research Sources",
        "description": "Research with emphasis on authoritative medical sources",
        "query": "What are the latest FDA-approved treatments for Type 2 diabetes? Prioritize official sources and peer-reviewed research.",
        "category": "authority",
        "expected_tools": ["web_search", "web_browse"],
    },
    {
        "id": "planning-security",
        "name": "Security Audit Plan",
        "description": "Create a security audit checklist",
        "query": "Develop a comprehensive security audit checklist for a web application handling financial data. Include OWASP considerations, compliance requirements (PCI-DSS), and remediation priorities.",
        "category": "planning",
        "expected_tools": ["web_search", "todo", "file_write"],
    },
    {
        "id": "info-rust-async",
        "name": "Rust Async Ecosystem",
        "description": "Deep dive into Rust async programming",
        "query": "Explain the Rust async ecosystem: tokio vs async-std, pin and futures, and best practices for building high-performance async applications.",
        "category": "information_seeking",
        "expected_tools": ["web_search", "web_browse"],
    },
    {
        "id": "verify-ai-claims",
        "name": "AI Benchmark Claims",
        "description": "Verify AI model performance claims",
        "query": "Verify GPT-4's claimed performance on various benchmarks (MMLU, HumanEval, etc.). Find the original sources and compare with independent evaluations.",
        "category": "verification",
        "expected_tools": ["web_search", "web_browse", "cross_validate", "reflect"],
    },
]


def get_scenarios():
    """Return all demo scenarios."""
    return DEMO_SCENARIOS


def get_scenario_by_id(scenario_id: str):
    """Get a specific scenario by ID."""
    for scenario in DEMO_SCENARIOS:
        if scenario["id"] == scenario_id:
            return scenario
    return None
