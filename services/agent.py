from typing import Literal, Dict, Any
from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
from services.db import Inventory, Cashflow, db
from datetime import datetime, UTC
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
import matplotlib.pyplot as plt
import io
import json
import base64
from sqlalchemy import text

# Define output schemas
class InventoryOutput(BaseModel):
    item_name: str = Field(description="Name of the inventory item")
    quantity: int = Field(description="Quantity of the item")
    price: float = Field(description="Price per unit")

class CashflowOutput(BaseModel):
    item_purpose: str = Field(description="Purpose of the transaction")
    amount: float = Field(description="Amount of money")
    credit_debit: Literal["credit", "debit"] = Field(description="Whether this is a credit or debit")

class QueryOutput(BaseModel):
    query: str

class VizTypeOutput(BaseModel):
    type: str

class RouterOutput(BaseModel):
    category: Literal["welcome", "inventory", "cashflow", "query", "graph"]
    message: str

class WhatsappResponse(BaseModel):
    message_type: Literal["text", "media"] 
    content: str
    caption: str = ""

# Initialize LLM
llm = ChatOllama(
    model="granite3.1-dense:8b",
    temperature=0,
    format='json',
)

# Router prompt
router_prompt = ChatPromptTemplate.from_messages([
    ("system", """Classify the user message into one of these categories:
    - welcome: General greetings like hi, hello
    - inventory: Messages about adding inventory items
    - cashflow: Messages about adding income/expenses
    - query: Messages requesting data/reports
    - graph: Messages requesting visual data/charts
    
    Respond with the category and the original message.
    Example: "add 5 apples at $2 each" -> {{"category": "inventory", "message": "add 5 apples at $2 each"}}"""),
    ("human", "{input}")
])

# Category-specific prompts
inventory_prompt = ChatPromptTemplate.from_messages([
    ("system", """Extract inventory information from the message.
    Expected output format: item name, quantity, and price.
    Example: "add 5 apples at $2 each" -> {{"item_name": "apples", "quantity": 5, "price": 2.0}}"""),
    ("human", "{input}")
])

cashflow_prompt = ChatPromptTemplate.from_messages([
    ("system", """Extract cashflow information from the message.
    Expected format: purpose, amount, and whether it's credit(income) or debit(expense).
    Example: "spent $50 on groceries" -> {{"item_purpose": "groceries", "amount": 50, "credit_debit": "debit"}}"""),
    ("human", "{input}")
])

query_prompt = ChatPromptTemplate.from_messages([
    ("system", """Generate a SQL query based on the user's question. 
    The database used is an SQLITE DB, so use SQLite specific functions only.
    Available tables: {tables}
    Schemas of the tables are: {schemas}
    Only use: SELECT statements. Also if user.id is needed, use this value {user_id}"""),
    ("human", "{input}")
])

# Processing functions
def process_welcome(message: str) -> WhatsappResponse:
    return WhatsappResponse(
        message_type="text",
        content="Hello! I'm your business assistant. How can I help you today?"
    )

def process_inventory(message: str, user_id: int) -> WhatsappResponse:
    # Parse inventory data
    # chain = inventory_prompt | llm
    chain = inventory_prompt | llm | PydanticOutputParser(pydantic_object=InventoryOutput)
    data = chain.invoke({"input": message})
    
        # Save to database
    new_inventory = Inventory(
        item_name=data.item_name,
        quantity=data.quantity,
        price=data.price,
        user_id=user_id
    )
    db.session.add(new_inventory)
    db.session.commit()
    
    return WhatsappResponse(
        message_type="text",
        content=f"Added {data.quantity} {data.item_name} at ${data.price} each to inventory."
    )

def process_cashflow(message: str, user_id: int) -> WhatsappResponse:
    # Parse cashflow data
    chain = cashflow_prompt | llm | PydanticOutputParser(pydantic_object=CashflowOutput)
    data = chain.invoke({"input": message})
    
    # Save to database
    new_cashflow = Cashflow(
        item_purpose=data.item_purpose,
        amount=data.amount,
        credit_debit=data.credit_debit,
        user_id=user_id,
        date=datetime.now(UTC)
    )
    db.session.add(new_cashflow)
    db.session.commit()
    
    return WhatsappResponse(
        message_type="text",
        content=f"Recorded {data.credit_debit}: ${data.amount} for {data.item_purpose}"
    )

def process_query(message: str, user_id: int) -> WhatsappResponse:
    # Generate SQL query
    ref_db = SQLDatabase.from_uri("sqlite:///database.db")
    toolkit = SQLDatabaseToolkit(db=ref_db, llm=llm)
    tools = toolkit.get_tools()

    list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
    get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

    tables = list_tables_tool.invoke("")
    schemas = {}
    for table in tables:
        schemas[table] = get_schema_tool.invoke(table)

    chain = query_prompt | llm | PydanticOutputParser(pydantic_object=QueryOutput)
    result = chain.invoke({"input": message, "user_id": user_id, "tables": tables, "schemas": json.dumps(schemas)})
    
    # Execute query with text() wrapper
    result = db.session.execute(text(result.query))
    columns = [col[0] for col in result.cursor.description]
    data = result.fetchall()
    
    return WhatsappResponse(
        message_type="text",
        content=str(data)
    )

def process_graph(message: str, user_id: int) -> WhatsappResponse:
    print('inside process_graph', message)
    # Get DB info
    ref_db = SQLDatabase.from_uri("sqlite:///database.db")
    toolkit = SQLDatabaseToolkit(db=ref_db, llm=llm)
    tools = toolkit.get_tools()

    list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
    get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")

    tables = list_tables_tool.invoke("")
    schemas = {}
    for table in tables:
        schemas[table] = get_schema_tool.invoke(table)

    # 1. Generate SQL query
    query_chain = ChatPromptTemplate.from_messages([
        ("system", """Generate a SQL query to get data for visualization based on the user's request.
        Available tables: {tables}
        Schemas: {schemas}
        Only use SELECT statements. If user_id is needed, use: {user_id}"""),
        ("human", "{input}")
    ]) | llm | PydanticOutputParser(pydantic_object=QueryOutput)

    query_result = query_chain.invoke({
        "input": message, 
        "user_id": user_id, 
        "tables": tables, 
        "schemas": json.dumps(schemas)
    })
    print('inside query_result', query_result)

    # 2. Determine graph type
    viz_chain = ChatPromptTemplate.from_messages([
        ("system", """Based on the SQL query and user request, suggest the most appropriate visualization type.
        Only respond with one of: line, bar, scatter, pie, hist
        Query: {query}"""),
        ("human", "{message}")
    ]) | llm | PydanticOutputParser(pydantic_object=VizTypeOutput)

    viz_type = viz_chain.invoke({"query": query_result.query, "message": message})
    print('inside viz_type', viz_type)

    # 3. Execute SQL query
    result = db.session.execute(text(query_result.query))
    columns = [col[0] for col in result.cursor.description]
    data = result.fetchall()
    print('inside data', data)
    print("types", columns)
    
    plt.switch_backend("Agg")
    # 4. Generate visualization
    plt.figure(figsize=(10, 6))
    
    # Convert SQL results to lists
    # columns = data[0].keys() if data else []
    values = list(zip(*[list(row) for row in data]))
    print("values", values)

    if viz_type.type == "line":
        plt.plot(values[0], values[1])
        plt.xticks(rotation=45)
    elif viz_type.type == "bar":
        plt.bar(values[0], values[1])
        plt.xticks(rotation=45)
    elif viz_type.type == "scatter":
        plt.scatter(values[0], values[1])
    elif viz_type.type == "pie":
        plt.pie(values[1], labels=values[0], autopct='%1.1f%%')
    elif viz_type.type == "hist":
        plt.hist(values[0], bins=20)

    plt.title(message)
    plt.tight_layout()

    # Save plot to bytes buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    plt.close()
    
    # Convert to base64
    image_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return WhatsappResponse(
        message_type="media",
        content=image_base64,
        caption=f"Here's your {viz_type} chart"
    )

def route_message(message: str, user_id: int) -> WhatsappResponse:
    # Classify message
    chain = router_prompt | llm | PydanticOutputParser(pydantic_object=RouterOutput)
    result = chain.invoke({"input": message})
    print("route_message", result)
    
    # Route to appropriate processor
    processors = {
        "welcome": process_welcome,
        "inventory": process_inventory,
        "cashflow": process_cashflow,
        "query": process_query,
        "graph": process_graph
    }
    
    processor = processors[result.category]
    return processor(result.message, user_id)

# Main chain
def process_whatsapp_message(message: str, user_id: int) -> Dict[str, Any]:
    """
    Main entry point for processing WhatsApp messages.
    Returns a dict with instructions for the WhatsApp sender functions.
    """
    response = route_message(message, user_id)
    
    return {
        "type": response.message_type,
        "content": response.content,
        "caption": response.caption if response.message_type == "media" else None
    }