"""
Knowledge Base Manager Page

This page allows users to:
1. Upload documents to domain-specific knowledge bases
2. View unsynced documents
3. Sync knowledge bases on demand
"""

import os
import sys
import streamlit as st
import tempfile
from datetime import datetime

# Add parent directory to path to import kb_manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.kb_manager import KnowledgeBaseManager, VALID_DOMAINS

# Set page configuration
st.set_page_config(
    page_title="Knowledge Base Manager",
    page_icon="📚",
    layout="wide"
)

# Initialize knowledge base manager
@st.cache_resource
def get_kb_manager():
    return KnowledgeBaseManager()

kb_manager = get_kb_manager()

# Navigation link back to main page
st.markdown("[← Back to Chat Interface](/)")

# Page header
st.title("Knowledge Base Manager")
st.markdown("""
This page allows you to manage domain-specific knowledge bases for the Advanced Computing Team Collaboration Swarm.
You can upload documents, view unsynced documents, and sync knowledge bases on demand.
""")

# Initialize tab index in session state if not already set
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 1  # Default to Unsynced Documents tab

# Create tabs
tabs = ["Upload Documents", "Unsynced Documents", "Knowledge Bases"]
tab1, tab2, tab3 = st.tabs(tabs)

# Tab 1: Upload Documents
with tab1:
    st.header("Upload Documents")
    
    # Domain selection
    domain = st.selectbox(
        "Select Domain",
        VALID_DOMAINS,
        format_func=lambda x: x.upper()
    )
    
    # File upload
    uploaded_files = st.file_uploader(
        "Upload Documents",
        accept_multiple_files=True,
        type=["pdf", "txt", "md", "docx", "csv", "json", "html"]
    )
    
    if uploaded_files:
        if st.button("Upload Selected Files"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Upload each file
            success_count = 0
            for i, uploaded_file in enumerate(uploaded_files):
                # Update progress
                progress = (i + 1) / len(uploaded_files)
                progress_bar.progress(progress)
                status_text.text(f"Uploading {uploaded_file.name}...")
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file.flush()
                    tmp_path = tmp_file.name
                
                try:
                    # Upload file with original name preserved
                    success, message = kb_manager.upload_file(tmp_path, domain, original_name=uploaded_file.name)
                    
                    # Remove temporary file
                    os.unlink(tmp_path)
                    
                    if success:
                        success_count += 1
                        st.success(f"✅ {uploaded_file.name}: {message}")
                    else:
                        st.error(f"❌ {uploaded_file.name}: {message}")
                except Exception as e:
                    # Remove temporary file
                    os.unlink(tmp_path)
                    st.error(f"❌ {uploaded_file.name}: {str(e)}")
            
            # Final status
            status_text.text(f"Uploaded {success_count} of {len(uploaded_files)} files")
            
            # Refresh unsynced documents
            st.session_state.refresh_unsynced = True

# Tab 2: Unsynced Documents
with tab2:
    st.header("Unsynced Documents")
    
    # Display success/error messages if they exist
    if "sync_success_message" in st.session_state:
        st.success(st.session_state.sync_success_message)
        del st.session_state.sync_success_message
    
    if "sync_error_message" in st.session_state:
        st.error(st.session_state.sync_error_message)
        del st.session_state.sync_error_message
        
    if "sync_all_message" in st.session_state:
        st.success(st.session_state.sync_all_message)
        del st.session_state.sync_all_message
    
    # Refresh and Clear buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Refresh") or st.session_state.get("refresh_unsynced", False):
            st.session_state.refresh_unsynced = False
            # Clear missing documents
            kb_manager.clear_missing_docs()
    with col2:
        if st.button("Clear All"):
            # Clear all unsynced documents
            kb_manager.unsynced_docs = {}
            kb_manager._save_unsynced_docs()
            st.success("All unsynced documents cleared")
            st.session_state.refresh_unsynced = True
    
    # Get unsynced documents
    unsynced_docs = kb_manager.get_unsynced_docs()
    
    if not unsynced_docs:
        st.info("No unsynced documents found")
    else:
        # Display unsynced documents by domain
        total_unsynced = 0
        for domain, docs in unsynced_docs.items():
            unsynced = [doc for doc in docs if not doc.get("synced", False)]
            if unsynced:
                st.subheader(f"{domain.upper()} - {len(unsynced)} unsynced documents")
                
                # Create table
                table_data = []
                for doc in unsynced:
                    upload_time = datetime.fromisoformat(doc["upload_time"]).strftime("%Y-%m-%d %H:%M:%S")
                    table_data.append([doc["file_name"], upload_time])
                
                st.table({"File Name": [row[0] for row in table_data], "Upload Time": [row[1] for row in table_data]})
                
                # Sync button
                if st.button(f"Sync {domain.upper()} Knowledge Base", key=f"sync_{domain}"):
                    with st.spinner(f"Syncing {domain.upper()} knowledge base..."):
                        success, message = kb_manager.sync_knowledge_base(domain)
                        if success:
                            st.session_state.sync_success_message = f"✅ {message}"
                            st.session_state.refresh_unsynced = True
                            st.session_state.active_tab = 1  # Keep on Unsynced Documents tab
                            st.rerun()
                        else:
                            st.session_state.sync_error_message = f"❌ {message}"
                            st.session_state.active_tab = 1  # Keep on Unsynced Documents tab
                            st.rerun()
                
                total_unsynced += len(unsynced)
        
        if total_unsynced == 0:
            st.success("All documents are synced")
        else:
            # Sync all button
            if st.button("Sync All Knowledge Bases"):
                st.session_state.active_tab = 1  # Keep on Unsynced Documents tab
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Get domains with unsynced documents
                domains_to_sync = []
                for domain, docs in unsynced_docs.items():
                    unsynced = [doc for doc in docs if not doc.get("synced", False)]
                    if unsynced:
                        domains_to_sync.append(domain)
                
                # Sync each domain
                success_count = 0
                for i, domain in enumerate(domains_to_sync):
                    # Update progress
                    progress = (i + 1) / len(domains_to_sync)
                    progress_bar.progress(progress)
                    status_text.text(f"Syncing {domain.upper()}...")
                    
                    # Sync knowledge base
                    success, message = kb_manager.sync_knowledge_base(domain)
                    if success:
                        success_count += 1
                        st.success(f"✅ {domain.upper()}: {message}")
                    else:
                        st.error(f"❌ {domain.upper()}: {message}")
                
                # Final status
                status_text.text(f"Synced {success_count} of {len(domains_to_sync)} knowledge bases")
                
                # Refresh unsynced documents
                st.session_state.refresh_unsynced = True
                st.session_state.sync_all_message = f"Synced {success_count} of {len(domains_to_sync)} knowledge bases"
                st.rerun()

# Tab 3: Knowledge Bases
with tab3:
    st.header("Knowledge Bases")
    
    # Refresh button
    if st.button("Refresh Knowledge Bases"):
        # Clear cache to force refresh
        kb_manager._kb_cache = None
        kb_manager._bucket_cache = None
        kb_manager._domain_map = None
    
    # Get knowledge bases
    kbs = kb_manager.list_knowledge_bases()
    
    if not kbs:
        st.warning("No knowledge bases found")
    else:
        # Display knowledge bases
        st.subheader(f"Found {len(kbs)} knowledge bases:")
        
        # Create table
        table_data = []
        for kb in kbs:
            table_data.append([kb["name"], kb["id"], kb["status"], kb["description"]])
        
        st.table({
            "Name": [row[0] for row in table_data],
            "ID": [row[1] for row in table_data],
            "Status": [row[2] for row in table_data],
            "Description": [row[3] for row in table_data]
        })
    
    # Get domain mapping
    domain_map = kb_manager.get_domain_map()
    
    if domain_map:
        st.subheader("Domain Mapping:")
        
        # Create table
        table_data = []
        for domain, info in domain_map.items():
            bucket = info.get("bucket", "N/A")
            kb_id = info.get("kb_id", "N/A")
            status = info.get("status", "N/A")
            table_data.append([domain.upper(), bucket, kb_id, status])
        
        st.table({
            "Domain": [row[0] for row in table_data],
            "S3 Bucket": [row[1] for row in table_data],
            "Knowledge Base ID": [row[2] for row in table_data],
            "Status": [row[3] for row in table_data]
        })