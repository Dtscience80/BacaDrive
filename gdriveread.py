"""
Streamlit Google Drive Reader App
Web aplikasi untuk membaca file dan folder Google Drive menggunakan Google OAuth

Requirements:
pip install streamlit google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client streamlit-oauth python-docx openpyxl PyPDF2 pandas plotly
"""

import streamlit as st
import os
import io
import json
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime

# Google API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

# File processing imports
import pandas as pd
from docx import Document
import PyPDF2
import csv
import plotly.express as px
import plotly.graph_objects as go

# Streamlit OAuth
from streamlit_oauth import OAuth1Component, OAuth2Component

class StreamlitGoogleDriveReader:
    """Streamlit Google Drive Reader with OAuth"""
    
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/userinfo.email'
        ]
        self.service = None
        
    def setup_oauth_config(self):
        """Setup OAuth configuration dari Streamlit secrets"""
        if 'google' not in st.secrets:
            st.error("""
            ❌ **Google OAuth belum dikonfigurasi!**
            
            Tambahkan konfigurasi berikut ke file `.streamlit/secrets.toml`:
            
            ```toml
            [google]
            client_id = "your-client-id.googleusercontent.com"
            client_secret = "your-client-secret"
            redirect_uri = "http://localhost:8501"
            ```
            """)
            st.stop()
            
        return {
            'client_id': st.secrets.google.client_id,
            'client_secret': st.secrets.google.client_secret,
            'redirect_uri': st.secrets.google.redirect_uri,
            'scope': ' '.join(self.scopes)
        }
    
    def authenticate_user(self):
        """Handle Google OAuth authentication"""
        oauth_config = self.setup_oauth_config()
        
        # Initialize OAuth2 component
        oauth2 = OAuth2Component(
            client_id=oauth_config['client_id'],
            client_secret=oauth_config['client_secret'],
            authorize_endpoint="https://accounts.google.com/o/oauth2/auth",
            token_endpoint="https://oauth2.googleapis.com/token",
            refresh_token_endpoint="https://oauth2.googleapis.com/token",
            revoke_token_endpoint="https://oauth2.googleapis.com/revoke",
        )
        
        # Check if user is already authenticated
        if 'auth_token' not in st.session_state:
            st.markdown("### 🔐 Login dengan Google untuk mengakses Drive")
            st.info("Klik tombol di bawah untuk login dan memberikan akses ke Google Drive Anda")
            
            # OAuth login button
            result = oauth2.authorize_button(
                name="Login dengan Google",
                icon="https://developers.google.com/identity/images/g-logo.png",
                redirect_uri=oauth_config['redirect_uri'],
                scope=oauth_config['scope'],
                key="google_auth",
                extras_params={"access_type": "offline", "prompt": "consent"}
            )
            
            if result and 'token' in result:
                st.session_state.auth_token = result['token']
                st.session_state.user_info = result.get('user_info', {})
                st.rerun()
        
        return st.session_state.get('auth_token')
    
    def build_service(self, token):
        """Build Google Drive service with token"""
        try:
            creds = Credentials(
                token=token['access_token'],
                refresh_token=token.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=st.secrets.google.client_id,
                client_secret=st.secrets.google.client_secret,
                scopes=self.scopes
            )
            
            self.service = build('drive', 'v3', credentials=creds)
            return True
            
        except Exception as e:
            st.error(f"❌ Error building service: {str(e)}")
            return False
    
    def get_folder_id_from_url(self, folder_url: str) -> str:
        """Extract folder ID from Google Drive URL"""
        if '/folders/' in folder_url:
            return folder_url.split('/folders/')[1].split('?')[0]
        else:
            raise ValueError("URL bukan folder Google Drive yang valid")
    
    def get_file_id_from_url(self, file_url: str) -> str:
        """Extract file ID from Google Drive URL"""
        if '/file/d/' in file_url:
            return file_url.split('/file/d/')[1].split('/')[0]
        elif 'id=' in file_url:
            return file_url.split('id=')[1].split('&')[0]
        else:
            raise ValueError("URL bukan file Google Drive yang valid")
    
    def list_files_in_folder(self, folder_id: str) -> List[Dict[str, Any]]:
        """Get list of files in folder"""
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink)",
                orderBy="name"
            ).execute()
            
            return results.get('files', [])
            
        except HttpError as error:
            st.error(f"❌ Error: {error}")
            return []
    
    def download_file(self, file_id: str) -> Optional[bytes]:
        """Download file from Google Drive"""
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            done = False
            
            while done is False:
                status, done = downloader.next_chunk()
            
            file_io.seek(0)
            return file_io.read()
            
        except HttpError as error:
            st.error(f"❌ Error downloading file: {error}")
            return None
    
    def export_google_doc(self, file_id: str, export_type: str = 'text/plain') -> Optional[str]:
        """Export Google Docs/Sheets/Slides"""
        try:
            request = self.service.files().export_media(fileId=file_id, mimeType=export_type)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            done = False
            
            while done is False:
                status, done = downloader.next_chunk()
            
            file_io.seek(0)
            return file_io.read().decode('utf-8')
            
        except HttpError as error:
            st.error(f"❌ Error exporting file: {error}")
            return None
    
    def read_file_content(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Read file content based on its type"""
        file_id = file_info['id']
        file_name = file_info['name']
        mime_type = file_info['mimeType']
        
        result = {
            'name': file_name,
            'id': file_id,
            'mime_type': mime_type,
            'content': None,
            'error': None,
            'web_link': file_info.get('webViewLink', '')
        }
        
        try:
            # Google Docs
            if mime_type == 'application/vnd.google-apps.document':
                content = self.export_google_doc(file_id, 'text/plain')
                result['content'] = content
                
            # Google Sheets
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                content = self.export_google_doc(file_id, 'text/csv')
                if content:
                    csv_reader = csv.reader(io.StringIO(content))
                    rows = list(csv_reader)
                    result['content'] = rows
                    
            # PDF Files
            elif mime_type == 'application/pdf':
                file_content = self.download_file(file_id)
                if file_content:
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    result['content'] = text
                    
            # Word Documents
            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                file_content = self.download_file(file_id)
                if file_content:
                    doc = Document(io.BytesIO(file_content))
                    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
                    result['content'] = text
                    
            # Excel Files
            elif mime_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                              'application/vnd.ms-excel']:
                file_content = self.download_file(file_id)
                if file_content:
                    df = pd.read_excel(io.BytesIO(file_content))
                    result['content'] = df
                    
            # Text Files
            elif mime_type.startswith('text/'):
                file_content = self.download_file(file_id)
                if file_content:
                    result['content'] = file_content.decode('utf-8')
                    
            # CSV Files
            elif mime_type == 'text/csv':
                file_content = self.download_file(file_id)
                if file_content:
                    csv_content = file_content.decode('utf-8')
                    csv_reader = csv.reader(io.StringIO(csv_content))
                    rows = list(csv_reader)
                    result['content'] = rows
                    
            # JSON Files
            elif mime_type == 'application/json':
                file_content = self.download_file(file_id)
                if file_content:
                    result['content'] = json.loads(file_content.decode('utf-8'))
                    
            else:
                result['error'] = f"Tipe file {mime_type} belum didukung"
                
        except Exception as e:
            result['error'] = str(e)
            
        return result

def display_file_content(content_data: Dict[str, Any]):
    """Display file content in Streamlit UI"""
    
    st.subheader(f"📄 {content_data['name']}")
    
    # File info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📁 Type", content_data['mime_type'].split('/')[-1].upper())
    with col2:
        if content_data['web_link']:
            st.markdown(f"🔗 [Buka di Drive]({content_data['web_link']})")
    with col3:
        if content_data['error']:
            st.error(f"❌ {content_data['error']}")
        else:
            st.success("✅ Berhasil dibaca")
    
    # Display content based on type
    if content_data['content'] and not content_data['error']:
        
        # Text content
        if isinstance(content_data['content'], str):
            st.text_area(
                "📝 Konten Text:", 
                content_data['content'], 
                height=300,
                key=f"text_{content_data['id']}"
            )
            
            # Word cloud for text
            if len(content_data['content']) > 100:
                words = content_data['content'].split()
                word_freq = pd.Series(words).value_counts().head(10)
                
                fig = px.bar(
                    x=word_freq.values,
                    y=word_freq.index,
                    orientation='h',
                    title="Top 10 Kata Paling Sering",
                    labels={'x': 'Frekuensi', 'y': 'Kata'}
                )
                st.plotly_chart(fig)
        
        # DataFrame content (Excel, CSV)
        elif isinstance(content_data['content'], pd.DataFrame):
            st.dataframe(content_data['content'])
            
            # Basic statistics for numeric columns
            numeric_cols = content_data['content'].select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                st.subheader("📊 Statistik Dasar")
                st.dataframe(content_data['content'][numeric_cols].describe())
                
                # Simple visualization
                if len(numeric_cols) >= 2:
                    col1, col2 = st.columns(2)
                    with col1:
                        x_col = st.selectbox("X-axis", numeric_cols, key=f"x_{content_data['id']}")
                    with col2:
                        y_col = st.selectbox("Y-axis", numeric_cols, key=f"y_{content_data['id']}")
                    
                    if x_col and y_col:
                        fig = px.scatter(content_data['content'], x=x_col, y=y_col)
                        st.plotly_chart(fig)
        
        # List content (CSV rows)
        elif isinstance(content_data['content'], list):
            if content_data['content']:
                df = pd.DataFrame(content_data['content'])
                st.dataframe(df)
            else:
                st.info("📄 File kosong")
        
        # JSON content
        elif isinstance(content_data['content'], dict):
            st.json(content_data['content'])
    
    st.divider()

def main():
    """Main Streamlit app"""
    
    # Page config
    st.set_page_config(
        page_title="Google Drive Reader",
        page_icon="📁",
        layout="wide"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #4285f4, #34a853, #fbbc05, #ea4335);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .file-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #4285f4;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📁 Google Drive Reader</h1>
        <p>Baca dan analisis file dari Google Drive Anda dengan mudah</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize reader
    reader = StreamlitGoogleDriveReader()
    
    # Authentication
    token = reader.authenticate_user()
    
    if not token:
        st.stop()
    
    # Build service
    if not reader.build_service(token):
        st.stop()
    
    # User info
    if 'user_info' in st.session_state:
        user_info = st.session_state.user_info
        st.sidebar.success(f"👋 Hello, {user_info.get('name', 'User')}!")
        
        # Logout button
        if st.sidebar.button("🚪 Logout"):
            for key in ['auth_token', 'user_info']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Main interface
    st.sidebar.header("⚙️ Pengaturan")
    
    # Mode selection
    mode = st.sidebar.radio(
        "Pilih mode:",
        ["📁 Baca Folder", "📄 Baca Single File"]
    )
    
    if mode == "📁 Baca Folder":
        st.header("📁 Baca Folder Google Drive")
        
        folder_url = st.text_input(
            "🔗 URL Folder Google Drive:",
            placeholder="https://drive.google.com/drive/folders/...",
            help="Paste URL folder Google Drive yang ingin dibaca"
        )
        
        if st.button("🚀 Baca Folder", type="primary"):
            if folder_url:
                try:
                    with st.spinner("📂 Membaca folder..."):
                        folder_id = reader.get_folder_id_from_url(folder_url)
                        files = reader.list_files_in_folder(folder_id)
                    
                    if files:
                        st.success(f"✅ Ditemukan {len(files)} file dalam folder")
                        
                        # Filter options
                        st.sidebar.subheader("🔍 Filter")
                        file_types = list(set([f['mimeType'] for f in files]))
                        selected_types = st.sidebar.multiselect(
                            "Tipe file:",
                            file_types,
                            default=file_types
                        )
                        
                        # Filter files
                        filtered_files = [f for f in files if f['mimeType'] in selected_types]
                        
                        # Progress bar
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Read files
                        results = []
                        for i, file in enumerate(filtered_files):
                            if file['mimeType'] != 'application/vnd.google-apps.folder':
                                status_text.text(f"📖 Membaca: {file['name']}")
                                content = reader.read_file_content(file)
                                results.append(content)
                                progress_bar.progress((i + 1) / len(filtered_files))
                        
                        status_text.text("✅ Selesai!")
                        
                        # Display results
                        st.header(f"📊 Hasil Pembacaan ({len(results)} files)")
                        
                        for content_data in results:
                            display_file_content(content_data)
                        
                    else:
                        st.warning("📁 Folder kosong atau tidak dapat diakses")
                        
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
            else:
                st.warning("⚠️ Masukkan URL folder terlebih dahulu")
    
    else:  # Single file mode
        st.header("📄 Baca Single File")
        
        file_url = st.text_input(
            "🔗 URL File Google Drive:",
            placeholder="https://drive.google.com/file/d/...",
            help="Paste URL file Google Drive yang ingin dibaca"
        )
        
        if st.button("📖 Baca File", type="primary"):
            if file_url:
                try:
                    with st.spinner("📄 Membaca file..."):
                        file_id = reader.get_file_id_from_url(file_url)
                        
                        # Get file info
                        file_info = reader.service.files().get(
                            fileId=file_id,
                            fields="id, name, mimeType, size, modifiedTime, webViewLink"
                        ).execute()
                        
                        content_data = reader.read_file_content(file_info)
                    
                    display_file_content(content_data)
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
            else:
                st.warning("⚠️ Masukkan URL file terlebih dahulu")
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **📋 Format yang didukung:**
    - Google Docs & Sheets
    - PDF, Word, Excel
    - Text, CSV, JSON
    - Dan lainnya...
    """)

if __name__ == "__main__":
    main()