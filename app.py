import os
import streamlit as st
import database

def initialise_database() -> None:
    database.create_tables()
    # Create default users
    database.create_default_users()
    # Will check whether any queries exist
    existing = database.fetch_queries()
    if existing.empty:
        csv_path = os.path.join(os.path.dirname(__file__), 'synthetic_client_queries.csv')
        try:
            database.import_csv(csv_path)
        except FileNotFoundError:
            pass

def main() -> None:
    """Top‑level function for the Streamlit app."""
    st.set_page_config(page_title='Client Query Management System', layout='wide')
    initialise_database()

    # Initialise session state variables
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'role' not in st.session_state:
        st.session_state.role = None
    if 'username' not in st.session_state:
        st.session_state.username = None

    st.title('Client Query Management System')

    if not st.session_state.logged_in:
        # Provide login interface
        st.subheader('Login')
        
        # Display default credentials
        st.info("""
        **Default Credentials:**
        - **Support Role**: Username: `support`, Password: `support123`
        - **Client Role**: Username: `client`, Password: `client123`
        """)
        
        role = st.selectbox('Select your role', ['Support', 'Client'], key='login_role')
        username = st.text_input('Username', key='login_username')
        password = st.text_input('Password', type='password', key='login_password')
        
        if st.button('Login'):
            # Attempt authentication using role-based credentials
            if database.authenticate_by_role_and_username(role, username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.success(f'Logged in as {username} ({role})')
                st.rerun()
            else:
                st.error('Invalid username or password for the selected role')

    else:
        # Display sidebar with logout option
        with st.sidebar:
            st.markdown(f"**Logged in as:** {st.session_state.username}\n\n**Role:** {st.session_state.role}")
            if st.button('Logout'):
                st.session_state.logged_in = False
                st.session_state.username = None
                st.session_state.role = None
                st.rerun()

        # Display role‑specific pages
        role = st.session_state.role
        if role == 'Client':
            st.header('Submit a New Query')
            mail_id = st.text_input('Email Address')
            mobile_number = st.text_input('Mobile Number')
            query_heading = st.text_input('Query Heading')
            query_description = st.text_area('Query Description')
            image_file = st.file_uploader('Attach an image (optional)', type=['png', 'jpg', 'jpeg'])
            if st.button('Submit Query'):
                if not mail_id or not mobile_number or not query_heading or not query_description:
                    st.warning('All fields except the image are required')
                else:
                    image_bytes = image_file.getvalue() if image_file else None
                    qid = database.insert_query(
                        mail_id=mail_id,
                        mobile_number=mobile_number,
                        query_heading=query_heading,
                        query_description=query_description,
                        image_bytes=image_bytes,
                    )
                    st.success(f'Query {qid} submitted successfully.')

        elif role == 'Support':
            st.header('Support Dashboard')
            status_filter = st.selectbox('Show queries with status', ['All', 'Opened', 'Closed'], key='status_filter')
            if status_filter == 'All':
                df = database.fetch_queries()
            else:
                df = database.fetch_queries(status_filter)
            st.subheader('Query List')
            st.dataframe(df)

            # Provide controls for closing open queries
            open_queries = df[df['status'] == 'Opened']['query_id'].tolist()
            if open_queries:
                st.subheader('Close an Open Query')
                selected_query = st.selectbox('Select a query to close', open_queries, key='close_select')
                if st.button('Close Selected Query'):
                    database.close_query(selected_query)
                    st.success(f'Query {selected_query} has been closed.')
                    st.rerun()
            else:
                st.info('There are no open queries to close.')

        else:
            st.error('Unknown role detected. Please log out and log in again.')


if __name__ == '__main__':
    main()