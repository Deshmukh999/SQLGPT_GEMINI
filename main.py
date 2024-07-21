import streamlit as st
import google.generativeai as genai
import tempfile
import os
import sqlite3
from dotenv import load_dotenv
from db_manager import DBManager

load_dotenv()

st.set_page_config(page_title='SQLGPT')
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro-latest')

prompt_model = """You are a human assistant, helping them write SQL queries according to their needs: Avoid including 
‘```’ or ‘sql’ in your response. Create tables based on user requirements, not the database name. After each query, 
Always end SQL queries with a semicolon. Use INTEGER PRIMARY KEY AUTOINCREMENT for primary keys. Don’t prompt users 
for table names. Always use Varchar datatype for text datatypes. Once you have created a table don't always create 
the same table just output the required code needed by the user. Provide SQL code exactly as requested. Avoid using 
variable names in syntax. If the user asks to create a table, provide only the SQL code for table creation. If the 
user asks to insert records, provide only the SQL code for inserting records without recreating the table. Name the 
variables or columns of the table using only small caps and underscores. Don't name the variable with underscore 
like _id unless the variable is named in the table."""

chat = model.start_chat(history=[])

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'executed_sql_commands' not in st.session_state:
    st.session_state['executed_sql_commands'] = set()
if 'db_path' not in st.session_state:
    st.session_state['db_path'] = 'dummy.db'
if 'files' not in st.session_state:
    st.session_state['files'] = []
if 'db_connection' not in st.session_state:
    st.session_state['db_connection'] = None
if 'show_sql_commands' not in st.session_state:
    st.session_state['show_sql_commands'] = set()


def get_sql_connection(db_path):
    try:
        if st.session_state['db_connection'] is not None:
            st.session_state['db_connection'].close()
        st.session_state['db_connection'] = DBManager(db_path)
    except sqlite3.OperationalError as e:
        st.error(f"Error connecting to database: {e}")


def gemini_response(user_input):
    response = chat.send_message([prompt_model, user_input])
    return response.text


def clean_sql_code(sql_code):
    if "```" in sql_code:
        sql_code = sql_code.replace("```sql", "").replace("```", "")
    return sql_code.strip()


def handle_sql_execution(sql_code):
    try:
        cleaned_response = clean_sql_code(sql_code)
        if cleaned_response not in st.session_state['executed_sql_commands']:
            st.session_state['db_connection'].execute_sql(cleaned_response)
            st.session_state['executed_sql_commands'].add(cleaned_response)
            st.success("SQL executed successfully")
        else:
            st.session_state['db_connection'].execute_sql(cleaned_response)
            executed_commands_list = list(st.session_state['executed_sql_commands'])
            while cleaned_response in executed_commands_list:
                executed_commands_list.remove(cleaned_response)
            st.session_state['executed_sql_commands'] = set(executed_commands_list)
    except Exception as e:
        flag = True
        st.error(f"SQL execution error: {e}")
        return flag


def conditional_duplicate_sql_queries(sql_code):
    try:
        cleaned_response = clean_sql_code(sql_code)
        if cleaned_response not in st.session_state['show_sql_commands']:
            st.session_state['show_sql_commands'].add(cleaned_response)
    except Exception:
        pass


def update_temp_file_with_committed_data(temp_file):
    temp_file.seek(0, os.SEEK_END)
    for command in st.session_state['executed_sql_commands']:
        temp_file.write((command + "\n").encode())
    temp_file.flush()


# Set the initial database connection
get_sql_connection(st.session_state['db_path'])
st.header('Chat with SQLGPT')
input_disabled = st.session_state.get('input_disabled', True)
st_input = st.chat_input('Chat with GEMINI!', disabled=input_disabled)

if st_input:
    response = gemini_response(st_input)
    st.session_state['chat_history'].append(("You", st_input))
    st.subheader('Response:')
    st.session_state['chat_history'].append(("GEMINI", response))
    handle_sql_execution(response)

with st.sidebar:
    st.title('Menu:')
    uploaded_files = st.file_uploader("Choose files", accept_multiple_files=True, type=['db', 'sqlite'])
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if not any(file['FileName'] == uploaded_file.name for file in st.session_state['files']):
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                temp_file.write(uploaded_file.read())
                temp_file.flush()
                st.session_state['files'].append(
                    {"FileName": uploaded_file.name, "Path": temp_file.name, "TempFile": temp_file}
                )

        st.session_state['input_disabled'] = False
    filenames = [file['FileName'] for file in st.session_state['files']]
    select_db = st.selectbox('Connect:', filenames)
    if select_db:
        st.session_state['db_path'] = next(
            file['Path'] for file in st.session_state['files'] if file['FileName'] == select_db)
        get_sql_connection(st.session_state['db_path'])
        st.session_state['input_disabled'] = False
    else:
        st.session_state['input_disabled'] = True
    for file in st.session_state['files']:
        with open(file=file['Path'], mode='rb') as filedata:
            filename = file['FileName']
            download_file = st.download_button(label=f'Download Committed {filename}', data=filedata,
                                               file_name=f'Committed {filename}',
                                               on_click=update_temp_file_with_committed_data, args=(file['TempFile'],))

for role, text in st.session_state['chat_history']:
    st.subheader(f'{role}:')
    text_parts = text.split('|')
    for part in text_parts:
        cleaned_part = clean_sql_code(part)
        if role == 'GEMINI' and cleaned_part in st.session_state['executed_sql_commands']:
            st.code(part, language='sql')
        else:
            st.markdown(part)
