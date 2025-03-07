from typing import Dict, List, Optional, Any, Tuple
import os
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
import langchain_core.runnables as runnable
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts.chat import MessagesPlaceholder

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

# Configure your model
llm = ChatOpenAI(model="gpt-4", temperature=0.2)

# Define state schema
class WorkflowState(BaseModel):
    """State for the development workflow agent."""
    user_inputs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User requirements and inputs")
    user_stories: Optional[List[Dict]] = Field(default_factory=list, description="Generated user stories")
    design_documents: Optional[Dict] = Field(default_factory=dict, description="Design documents")
    code: Optional[Dict] = Field(default_factory=dict, description="Generated code")
    test_cases: Optional[List[Dict]] = Field(default_factory=list, description="Test cases")
    qa_results: Optional[Dict] = Field(default_factory=dict, description="QA testing results")
    maintenance_notes: Optional[List[str]] = Field(default_factory=list, description="Maintenance and update notes")
    current_step: str = Field(default="collect_requirements", description="Current step in the workflow")
    history: List[Dict] = Field(default_factory=list, description="Conversation history")
    feedback: Optional[Dict] = Field(default_factory=dict, description="Feedback for various stages")

# Utility function to add to history
def add_to_history(state: Dict, actor: str, message: str) -> Dict:
    """Add a message to the conversation history."""
    state["history"].append({
        "actor": actor,
        "message": message,
        "timestamp": datetime.now().isoformat()
    })
    return state

# Node functions
def collect_requirements(state: Dict) -> Dict:
    """Collect user requirements and inputs."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a requirements gathering specialist. Ask the user specific questions 
        about their project requirements. Extract detailed information about:
        1. Project goals and objectives
        2. Target users and stakeholders
        3. Functional requirements
        4. Non-functional requirements (performance, security, etc.)
        5. Constraints and limitations
        
        Format your response as a detailed requirements document."""),
        MessagesPlaceholder(variable_name="history"),
        ("human", "Please provide your project requirements.")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"history": state.get("history", [])})
    
    state["user_inputs"]["requirements_document"] = response.content
    state = add_to_history(state, "ai", f"Requirements collected: {response.content[:100]}...")
    state["current_step"] = "generate_user_stories"
    
    return state

def generate_user_stories(state: Dict) -> Dict:
    """Generate user stories based on requirements."""
    requirements = state["user_inputs"].get("requirements_document", "")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a product analyst specialized in creating user stories.
        Based on the provided requirements, generate comprehensive user stories following the format:
        
        As a [type of user], I want [an action] so that [a benefit/value].
        
        Create at least 5 detailed user stories that cover the core functionality.
        For each story, include acceptance criteria."""),
        ("human", f"Generate user stories based on these requirements: {requirements}")
    ])
    
    class UserStory(BaseModel):
        id: str = Field(description="Unique identifier for the user story (US-XXX)")
        user_type: str = Field(description="Type of user")
        action: str = Field(description="What the user wants to do")
        benefit: str = Field(description="The benefit or value to the user")
        acceptance_criteria: List[str] = Field(description="List of acceptance criteria")
        priority: str = Field(description="Priority (High, Medium, Low)")
    
    class UserStoriesOutput(BaseModel):
        user_stories: List[UserStory] = Field(description="List of user stories")
        
    parser = JsonOutputParser(pydantic_object=UserStoriesOutput)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["user_stories"] = result["user_stories"]
    state = add_to_history(state, "ai", f"Generated {len(result['user_stories'])} user stories")
    state["current_step"] = "product_owner_review"
    
    return state

def product_owner_review(state: Dict) -> Dict:
    """Simulate a product owner review."""
    user_stories = state["user_stories"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a product owner reviewing user stories.
        Critically evaluate each user story for clarity, completeness, and alignment with project goals.
        Provide specific feedback for improvement or approval."""),
        ("human", f"Review these user stories: {user_stories}")
    ])
    
    class ReviewResult(BaseModel):
        approved: bool = Field(description="Whether the stories are approved overall")
        feedback: Dict[str, str] = Field(description="Feedback for each story by ID")
        
    parser = JsonOutputParser(pydantic_object=ReviewResult)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    
    state["feedback"]["product_owner"] = result
    state = add_to_history(state, "ai", 
                          f"Product owner review: {'Approved' if result['approved'] else 'Needs revision'}")
    
    # Determine next step based on approval
    if result["approved"]:
        state["current_step"] = "create_design_documents"
    else:
        state["current_step"] = "revise_user_stories"
    
    return state

def revise_user_stories(state: Dict) -> Dict:
    """Revise user stories based on feedback."""
    user_stories = state["user_stories"]
    feedback = state["feedback"]["product_owner"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a product analyst revising user stories based on feedback.
        Update each story to address the specific feedback provided.
        Ensure all stories are clear, complete, and align with project goals."""),
        ("human", f"Revise these user stories: {user_stories}\n\nBased on this feedback: {feedback}")
    ])
    
    class UserStory(BaseModel):
        id: str = Field(description="Unique identifier for the user story (US-XXX)")
        user_type: str = Field(description="Type of user")
        action: str = Field(description="What the user wants to do")
        benefit: str = Field(description="The benefit or value to the user")
        acceptance_criteria: List[str] = Field(description="List of acceptance criteria")
        priority: str = Field(description="Priority (High, Medium, Low)")
    
    class UserStoriesOutput(BaseModel):
        user_stories: List[UserStory] = Field(description="List of revised user stories")
        
    parser = JsonOutputParser(pydantic_object=UserStoriesOutput)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["user_stories"] = result["user_stories"]
    state = add_to_history(state, "ai", "User stories revised based on feedback")
    state["current_step"] = "product_owner_review"
    
    return state

def create_design_documents(state: Dict) -> Dict:
    """Create design documents based on approved user stories."""
    user_stories = state["user_stories"]
    requirements = state["user_inputs"].get("requirements_document", "")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a software architect creating design documents.
        Based on the requirements and user stories, create comprehensive design documents including:
        
        1. System architecture overview
        2. Component diagrams
        3. Data models
        4. API specifications
        5. Technical considerations and constraints
        
        Be detailed and specific in your design decisions."""),
        ("human", f"Create design documents based on these requirements: {requirements}\n\nAnd these user stories: {user_stories}")
    ])
    
    class DesignDocuments(BaseModel):
        system_architecture: Dict = Field(description="System architecture overview")
        components: List[Dict] = Field(description="Component descriptions and diagrams")
        data_models: List[Dict] = Field(description="Data models and relationships")
        api_specifications: List[Dict] = Field(description="API endpoints and specifications")
        technical_considerations: List[str] = Field(description="Technical considerations and constraints")
        
    parser = JsonOutputParser(pydantic_object=DesignDocuments)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["design_documents"] = result
    state = add_to_history(state, "ai", "Design documents created")
    state["current_step"] = "design_review"
    
    return state

def design_review(state: Dict) -> Dict:
    """Simulate a design review."""
    design_docs = state["design_documents"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a senior software architect reviewing design documents.
        Critically evaluate the architecture, components, data models, and API specifications.
        Consider scalability, security, maintainability, and alignment with requirements.
        Provide specific feedback for improvement or approval."""),
        ("human", f"Review these design documents: {design_docs}")
    ])
    
    class ReviewResult(BaseModel):
        approved: bool = Field(description="Whether the design is approved overall")
        feedback: Dict[str, List[str]] = Field(description="Feedback for each section")
        
    parser = JsonOutputParser(pydantic_object=ReviewResult)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    
    state["feedback"]["design_review"] = result
    state = add_to_history(state, "ai", 
                          f"Design review: {'Approved' if result['approved'] else 'Needs revision'}")
    
    # Determine next step based on approval
    if result["approved"]:
        state["current_step"] = "generate_code"
    else:
        state["current_step"] = "revise_design_documents"
    
    return state

def revise_design_documents(state: Dict) -> Dict:
    """Revise design documents based on feedback."""
    design_docs = state["design_documents"]
    feedback = state["feedback"]["design_review"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a software architect revising design documents based on feedback.
        Update each section to address the specific feedback provided.
        Ensure the design is scalable, secure, maintainable, and aligns with requirements."""),
        ("human", f"Revise these design documents: {design_docs}\n\nBased on this feedback: {feedback}")
    ])
    
    class DesignDocuments(BaseModel):
        system_architecture: Dict = Field(description="System architecture overview")
        components: List[Dict] = Field(description="Component descriptions and diagrams")
        data_models: List[Dict] = Field(description="Data models and relationships")
        api_specifications: List[Dict] = Field(description="API endpoints and specifications")
        technical_considerations: List[str] = Field(description="Technical considerations and constraints")
        
    parser = JsonOutputParser(pydantic_object=DesignDocuments)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["design_documents"] = result
    state = add_to_history(state, "ai", "Design documents revised based on feedback")
    state["current_step"] = "design_review"
    
    return state

def generate_code(state: Dict) -> Dict:
    """Generate code based on approved design documents."""
    design_docs = state["design_documents"]
    user_stories = state["user_stories"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert software developer generating code based on design documents and user stories.
        Create implementation code for the key components of the system.
        Follow best practices for the target technologies, including proper error handling,
        documentation, and testing considerations."""),
        ("human", f"Generate code based on these design documents: {design_docs}\n\nTo implement these user stories: {user_stories}")
    ])
    
    class CodeBase(BaseModel):
        components: Dict[str, str] = Field(description="Code for each component")
        file_structure: Dict[str, List[str]] = Field(description="File structure for the codebase")
        setup_instructions: List[str] = Field(description="Instructions for setting up the codebase")
        
    parser = JsonOutputParser(pydantic_object=CodeBase)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["code"] = result
    state = add_to_history(state, "ai", "Code generated for implementation")
    state["current_step"] = "code_review"
    
    return state

def code_review(state: Dict) -> Dict:
    """Simulate a code review."""
    code = state["code"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a senior developer conducting a code review.
        Critically evaluate the code for:
        1. Correctness and functionality
        2. Code quality and best practices
        3. Security considerations
        4. Performance implications
        5. Maintainability and readability
        
        Provide specific feedback for improvement or approval."""),
        ("human", f"Review this code: {code}")
    ])
    
    class ReviewResult(BaseModel):
        approved: bool = Field(description="Whether the code is approved overall")
        feedback: Dict[str, List[str]] = Field(description="Feedback for each component")
        security_issues: List[Dict] = Field(description="Potential security issues identified")
        
    parser = JsonOutputParser(pydantic_object=ReviewResult)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    
    state["feedback"]["code_review"] = result
    state = add_to_history(state, "ai", 
                          f"Code review: {'Approved' if result['approved'] else 'Needs revision'}")
    
    # Determine next step based on approval
    if result["approved"]:
        state["current_step"] = "security_review"
    else:
        state["current_step"] = "fix_code_after_review"
    
    return state

def fix_code_after_review(state: Dict) -> Dict:
    """Fix code based on review feedback."""
    code = state["code"]
    feedback = state["feedback"]["code_review"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a software developer fixing code based on review feedback.
        Address each specific issue raised in the feedback.
        Ensure the code is correct, follows best practices, and is maintainable."""),
        ("human", f"Fix this code: {code}\n\nBased on this feedback: {feedback}")
    ])
    
    class CodeBase(BaseModel):
        components: Dict[str, str] = Field(description="Updated code for each component")
        file_structure: Dict[str, List[str]] = Field(description="File structure for the codebase")
        setup_instructions: List[str] = Field(description="Instructions for setting up the codebase")
        changes_made: Dict[str, List[str]] = Field(description="Summary of changes made to address feedback")
        
    parser = JsonOutputParser(pydantic_object=CodeBase)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["code"] = result
    state = add_to_history(state, "ai", "Code fixed based on review feedback")
    state["current_step"] = "code_review"
    
    return state

def security_review(state: Dict) -> Dict:
    """Simulate a security review of the code."""
    code = state["code"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a security expert conducting a security review of the code.
        Analyze the code for:
        1. Common security vulnerabilities (OWASP Top 10, etc.)
        2. Data protection and privacy concerns
        3. Authentication and authorization issues
        4. Input validation and sanitization
        5. Secure coding practices
        
        Provide specific feedback for security improvements or approval."""),
        ("human", f"Conduct a security review of this code: {code}")
    ])
    
    class SecurityReviewResult(BaseModel):
        approved: bool = Field(description="Whether the code passes security review")
        vulnerabilities: List[Dict] = Field(description="Identified security vulnerabilities")
        recommendations: List[str] = Field(description="Security improvement recommendations")
        
    parser = JsonOutputParser(pydantic_object=SecurityReviewResult)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    
    state["feedback"]["security_review"] = result
    state = add_to_history(state, "ai", 
                          f"Security review: {'Approved' if result['approved'] else 'Security issues found'}")
    
    # Determine next step based on approval
    if result["approved"]:
        state["current_step"] = "write_test_cases"
    else:
        state["current_step"] = "fix_code_after_security"
    
    return state

def fix_code_after_security(state: Dict) -> Dict:
    """Fix code based on security review feedback."""
    code = state["code"]
    feedback = state["feedback"]["security_review"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a security-focused developer fixing code based on security review feedback.
        Address each vulnerability and implement the recommended security improvements.
        Ensure the code follows secure coding practices and addresses all security concerns."""),
        ("human", f"Fix security issues in this code: {code}\n\nBased on this security review: {feedback}")
    ])
    
    class CodeBase(BaseModel):
        components: Dict[str, str] = Field(description="Updated code for each component")
        file_structure: Dict[str, List[str]] = Field(description="File structure for the codebase")
        setup_instructions: List[str] = Field(description="Instructions for setting up the codebase")
        security_fixes: Dict[str, List[str]] = Field(description="Summary of security fixes implemented")
        
    parser = JsonOutputParser(pydantic_object=CodeBase)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["code"] = result
    state = add_to_history(state, "ai", "Code fixed based on security review")
    state["current_step"] = "security_review"
    
    return state

def write_test_cases(state: Dict) -> Dict:
    """Write test cases based on user stories and code."""
    user_stories = state["user_stories"]
    code = state["code"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a QA engineer writing test cases.
        Based on the user stories and implementation code, create comprehensive test cases including:
        1. Unit tests for individual components
        2. Integration tests for component interactions
        3. System tests for end-to-end functionality
        4. Edge cases and error handling tests
        
        For each test case, include test steps, expected results, and prerequisites."""),
        ("human", f"Create test cases for this code: {code}\n\nBased on these user stories: {user_stories}")
    ])
    
    class TestCase(BaseModel):
        id: str = Field(description="Unique identifier for the test case (TC-XXX)")
        name: str = Field(description="Name of the test case")
        description: str = Field(description="Description of what is being tested")
        test_type: str = Field(description="Type of test (Unit, Integration, System, etc.)")
        prerequisites: List[str] = Field(description="Prerequisites for running the test")
        test_steps: List[str] = Field(description="Steps to execute the test")
        expected_results: List[str] = Field(description="Expected results for each step")
        related_user_stories: List[str] = Field(description="IDs of related user stories")
    
    class TestCasesOutput(BaseModel):
        test_cases: List[TestCase] = Field(description="List of test cases")
        test_coverage: Dict[str, float] = Field(description="Test coverage metrics")
        
    parser = JsonOutputParser(pydantic_object=TestCasesOutput)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["test_cases"] = result["test_cases"]
    state = add_to_history(state, "ai", f"Created {len(result['test_cases'])} test cases")
    state["current_step"] = "test_cases_review"
    
    return state

def test_cases_review(state: Dict) -> Dict:
    """Simulate a review of test cases."""
    test_cases = state["test_cases"]
    user_stories = state["user_stories"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a QA lead reviewing test cases.
        Evaluate the test cases for:
        1. Comprehensiveness and coverage of requirements
        2. Clarity and executability
        3. Edge case and error handling coverage
        4. Alignment with user stories
        
        Provide specific feedback for improvement or approval."""),
        ("human", f"Review these test cases: {test_cases}\n\nAgainst these user stories: {user_stories}")
    ])
    
    class ReviewResult(BaseModel):
        approved: bool = Field(description="Whether the test cases are approved overall")
        feedback: Dict[str, List[str]] = Field(description="Feedback for test cases by ID")
        missing_coverage: List[str] = Field(description="Areas with missing test coverage")
        
    parser = JsonOutputParser(pydantic_object=ReviewResult)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    
    state["feedback"]["test_cases_review"] = result
    state = add_to_history(state, "ai", 
                          f"Test cases review: {'Approved' if result['approved'] else 'Needs revision'}")
    
    # Determine next step based on approval
    if result["approved"]:
        state["current_step"] = "qa_testing"
    else:
        state["current_step"] = "fix_test_cases"
    
    return state

def fix_test_cases(state: Dict) -> Dict:
    """Fix test cases based on review feedback."""
    test_cases = state["test_cases"]
    feedback = state["feedback"]["test_cases_review"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a QA engineer fixing test cases based on review feedback.
        Address each specific issue raised in the feedback.
        Ensure the test cases are comprehensive, clear, and align with user stories."""),
        ("human", f"Fix these test cases: {test_cases}\n\nBased on this feedback: {feedback}")
    ])
    
    class TestCase(BaseModel):
        id: str = Field(description="Unique identifier for the test case (TC-XXX)")
        name: str = Field(description="Name of the test case")
        description: str = Field(description="Description of what is being tested")
        test_type: str = Field(description="Type of test (Unit, Integration, System, etc.)")
        prerequisites: List[str] = Field(description="Prerequisites for running the test")
        test_steps: List[str] = Field(description="Steps to execute the test")
        expected_results: List[str] = Field(description="Expected results for each step")
        related_user_stories: List[str] = Field(description="IDs of related user stories")
    
    class TestCasesOutput(BaseModel):
        test_cases: List[TestCase] = Field(description="List of revised test cases")
        changes_made: Dict[str, List[str]] = Field(description="Summary of changes made to address feedback")
        
    parser = JsonOutputParser(pydantic_object=TestCasesOutput)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["test_cases"] = result["test_cases"]
    state = add_to_history(state, "ai", "Test cases revised based on feedback")
    state["current_step"] = "test_cases_review"
    
    return state

def qa_testing(state: Dict) -> Dict:
    """Simulate QA testing of the code against test cases."""
    code = state["code"]
    test_cases = state["test_cases"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a QA tester executing test cases against the implemented code.
        For each test case:
        1. Determine if it passes or fails
        2. Document any issues or defects found
        3. Provide specific details about failures
        
        Summarize the overall test results and recommendation."""),
        ("human", f"Test this code: {code}\n\nUsing these test cases: {test_cases}")
    ])
    
    class TestResult(BaseModel):
        test_case_id: str = Field(description="ID of the test case")
        status: str = Field(description="Status (Pass/Fail)")
        issues: List[str] = Field(description="Issues found if failed")
    
    class TestingResults(BaseModel):
        passed: bool = Field(description="Whether all tests passed")
        results: List[TestResult] = Field(description="Results for each test case")
        defects: List[Dict] = Field(description="Detailed defects found")
        pass_rate: float = Field(description="Percentage of tests that passed")
        
    parser = JsonOutputParser(pydantic_object=TestingResults)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["qa_results"] = result
    state = add_to_history(state, "ai", 
                          f"QA testing: {'Passed' if result['passed'] else 'Failed'} with {result['pass_rate']}% pass rate")
    
    # Determine next step based on test results
    if result["passed"]:
        state["current_step"] = "deployment"
    else:
        state["current_step"] = "fix_code_after_qa"
    
    return state

def fix_code_after_qa(state: Dict) -> Dict:
    """Fix code based on QA testing results."""
    code = state["code"]
    qa_results = state["qa_results"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a developer fixing code based on QA testing results.
        Address each defect and failed test case.
        Ensure the code passes all test cases and functions as expected."""),
        ("human", f"Fix this code: {code}\n\nBased on these QA results: {qa_results}")
    ])
    
    class CodeBase(BaseModel):
        components: Dict[str, str] = Field(description="Updated code for each component")
        file_structure: Dict[str, List[str]] = Field(description="File structure for the codebase")
        setup_instructions: List[str] = Field(description="Instructions for setting up the codebase")
        fixes: Dict[str, str] = Field(description="Fixes implemented for each defect")
        
    parser = JsonOutputParser(pydantic_object=CodeBase)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["code"] = result
    state = add_to_history(state, "ai", "Code fixed based on QA testing results")
    state["current_step"] = "qa_testing"
    
    return state

def deployment(state: Dict) -> Dict:
    """Simulate deployment of the code."""
    code = state["code"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a DevOps engineer deploying code to production.
        Create a deployment plan including:
        1. Deployment strategy (blue-green, canary, etc.)
        2. Environment configuration
        3. Rollback plan
        4. Monitoring setup
        
        Document the deployment process and outcome."""),
        ("human", f"Create a deployment plan for this code: {code}")
    ])
    
    class DeploymentPlan(BaseModel):
        strategy: str = Field(description="Deployment strategy")
        environments: Dict[str, Dict] = Field(description="Environment configurations")
        steps: List[str] = Field(description="Deployment steps")
        rollback_plan: List[str] = Field(description="Rollback plan")
        monitoring: Dict[str, List[str]] = Field(description="Monitoring setup")
        deployment_outcome: str = Field(description="Outcome of the deployment")
        
    parser = JsonOutputParser(pydantic_object=DeploymentPlan)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["deployment_plan"] = result
    state = add_to_history(state, "ai", "Deployment plan created and executed")
    state["current_step"] = "monitoring"
    
    return state

def monitoring(state: Dict) -> Dict:
    """Simulate monitoring of the deployed application."""
    deployment_plan = state.get("deployment_plan", {})
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a monitoring specialist tracking the performance of a deployed application.
        Collect and analyze:
        1. System performance metrics
        2. Error rates and logs
        3. User feedback and satisfaction
        4. Business metrics
        
        Provide insights and recommendations based on the monitoring data."""),
        ("human", f"Monitor the application deployed with this plan: {deployment_plan}")
    ])
    
    class MonitoringResults(BaseModel):
        metrics: Dict[str, Dict] = Field(description="Key performance metrics")
        alerts: List[Dict] = Field(description="Alerts triggered")
        user_feedback: Dict[str, float] = Field(description="User feedback metrics")
        insights: List[str] = Field(description="Insights from monitoring")
        recommendations: List[str] = Field(description="Recommendations for improvements")
        
    parser = JsonOutputParser(pydantic_object=MonitoringResults)
    chain = prompt | llm | parser
    
    result = chain.invoke({})
    state["monitoring_results"] = result
    state = add_to_history(state, "ai", "Monitoring data collected and analyzed")
    state["current_step"] = "maintenance"
    
    return state

def maintenance(state: Dict) -> Dict:
    """Plan and implement maintenance and updates."""
    code = state["code"]
    monitoring_results = state.get("monitoring_results", {})
    user_feedback = monitoring_results.get("user_feedback", {})
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a software maintenance engineer planning updates and improvements.
        Based on monitoring data and user feedback:
        1. Identify areas for improvement
        2. Prioritize maintenance tasks
        3. Plan feature enhancements
        4. Schedule regular maintenance activities
        
        Create a comprehensive maintenance plan."""),
        ("human", f"Create a maintenance plan for this code: {code}\n\nBased on these monitoring results: {monitoring_results}")
    ])
    
    class MaintenancePlan(BaseModel):
        improvements: List[Dict] = Field(description="Planned improvements")
        bug_fixes: List[Dict] = Field(description="Bug fixes to implement")
        feature_enhancements: List[Dict] = Field(description="Feature enhancements to develop")
        scheduled_maintenance: Dict[str, List[str]] = Field(description="Scheduled maintenance