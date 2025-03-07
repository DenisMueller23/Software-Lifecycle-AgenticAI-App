# Project Root Directory Structure
project_root/
├── README.md                  # Project documentation and setup instructions
├── .gitignore                 # Git ignore file
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Modern Python packaging
├── .env.example               # Example environment variables (template)
├── config/                    # Configuration files
│   ├── __init__.py
│   ├── settings.py            # General application settings
│   └── prompts/               # Organized prompt templates
│       ├── __init__.py
│       ├── requirements.py    # Requirements gathering prompts
│       ├── user_stories.py    # User story prompts
│       ├── design.py          # Design document prompts
│       ├── code.py            # Code generation prompts
│       ├── testing.py         # Test case prompts
│       └── deployment.py      # Deployment prompts
├── src/                       # Main source code
│   ├── __init__.py
│   ├── main.py                # Application entry point
│   ├── models/                # Data models
│   │   ├── __init__.py
│   │   ├── schema.py          # State schema definitions
│   │   └── output_parsers.py  # Output parsers for different stages
│   ├── agents/                # Agent definitions
│   │   ├── __init__.py
│   │   ├── base_agent.py      # Base agent functionality
│   │   ├── requirements_agent.py
│   │   ├── design_agent.py
│   │   ├── coding_agent.py
│   │   ├── testing_agent.py
│   │   └── deployment_agent.py
│   ├── nodes/                 # Graph nodes for workflow
│   │   ├── __init__.py
│   │   ├── requirements.py    # Requirements gathering nodes
│   │   ├── user_stories.py    # User story nodes
│   │   ├── design.py          # Design document nodes
│   │   ├── code.py            # Code generation nodes
│   │   ├── testing.py         # Test case nodes
│   │   └── deployment.py      # Deployment nodes
│   ├── workflows/             # LangGraph workflow definitions
│   │   ├── __init__.py
│   │   ├── dev_workflow.py    # Main development workflow
│   │   └── feedback_loop.py   # Feedback integration workflows
│   └── utils/                 # Utility functions
│       ├── __init__.py
│       ├── logger.py          # Logging utilities
│       ├── state_helpers.py   # State management helpers
│       └── validators.py      # Input validation helpers
├── artifacts/                 # Storage for generated artifacts
│   ├── requirements/          # Requirements documents
│   ├── user_stories/          # User stories
│   ├── designs/               # Design documents
│   ├── code/                  # Generated code
│   └── tests/                 # Test cases
├── tests/                     # Tests for the agent system itself
│   ├── __init__.py
│   ├── conftest.py            # Pytest configuration
│   ├── test_agents/           # Tests for agent functionality
│   ├── test_workflows/        # Tests for workflow integrations
│   └── test_nodes/            # Tests for individual nodes
└── examples/                  # Example usage and demos
    ├── simple_project.py      # Simple project example
    └── complex_workflow.py    # Complex workflow example
