"""
Streamlit Google Drive Reader App - Fixed Version
Web aplikasi untuk membaca file dan folder Google Drive menggunakan Google OAuth

Requirements:
pip install streamlit google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-docx openpyxl PyPDF2 pandas plotly streamlit-components-custom
"""

import streamlit as st
import os
import io
import json
import urllib.parse
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

class StreamlitGoogleDriveReader:
    """Streamlit Google Drive Reader with Manual OAuth Implementation"""
    
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/userinfo.email'
        ]
        self.service = None
        
    def get_base_url(self):
        """Get the base URL for the app"""
        try:
            # Try to detect Streamlit Cloud
            if 'STREAMLIT_SHARING' in os.environ or 'streamlit.app' in str(st.get_option('server.baseUrlPath')):
                # For Streamlit Cloud, construct URL from environment or use a default
                app_name = os.environ.get('STREAMLIT_APP_NAME', 'your-app-name')
                return f"https://{app_name}.streamlit.app"
            else:
                return "http://localhost:8501"
        except:
            return "http://localhost:8501"
        
    def setup_oauth_config(self):
        """Setup OAuth configuration dari Streamlit secrets"""
        if 'google' not in st.secrets:
            st.error("""
            ❌ **Google OAuth belum dikonfigurasi!**
            
            Tambahkan konfigurasi berikut ke Streamlit secrets:
            
            ```toml
            [google]
            client_id = "your-client-id.googleusercontent.com"
            client_secret = "your-client-secret"
            ```
            
            **Setup Instructions:**
            1. Buka Google Cloud Console
            2. Buat OAuth2 credentials (Web Application)
            3. Tambahkan authorized redirect URI: `{self.get_base_url()}`
            4. Copy client_id dan client_secret ke Streamlit secrets
            """)
            st.stop()
            
        base_url = self.get_base_url()
        
        return {
            'client_id': st.secrets.google.client_id,
            'client_secret': st.secrets.google.client_secret,
            'redirect_uri': base_url,
            'scope': ' '.join(self.scopes)
        }
    
    def get_authorization_url(self):
        """Generate OAuth authorization URL"""
        oauth_config = self.setup_oauth_config()
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": oauth_config['client_id'],
                    "client_secret": oauth_config['client_secret'],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [oauth_config['redirect_uri']]
                }
            },
            scopes=self.scopes
        )
        
        flow.redirect_uri = oauth_config['redirect_uri']
        
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Store state in session
        st.session_state.oauth_state = state
        
        return auth_url
    
    def handle_oauth_callback(self):
        """Handle OAuth callback and get tokens"""
        # Get authorization code from URL parameters
        query_params = st.experimental_get_query_params()
        
        if 'code' in query_params and 'state' in query_params:
            auth_code = query_params['code'][0]
            returned_state = query_params['state'][0]
            
            # Verify state parameter
            if st.session_state.get('oauth_state') != returned_state:
                st.error("❌ Invalid OAuth state parameter")
                return None
            
            try:
                oauth_config = self.setup_oauth_config()
                
                # Create OAuth flow
                flow = Flow.from_client_config(
                    {
                        "web": {
                            "client_id": oauth_config['client_id'],
                            "client_secret": oauth_config['client_secret'],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "redirect_uris": [oauth_config['redirect_uri']]
                        }
                    },
                    scopes=self.scopes
                )
                
                flow.redirect_uri = oauth_config['redirect_uri']
                
                # Exchange authorization code for tokens
                flow.fetch_token(code=auth_code)
                
                # Get credentials
                creds = flow.credentials
                
                # Store tokens in session
                token_data = {
                    'access_token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'expires_in': 3600  # Default expiry
                }
                
                st.session_state.auth_token = token_data
                
                # Get user info
                try:
                    user_service = build('oauth2', 'v2', credentials=creds)
                    user_info = user_service.userinfo().get().execute()
                    st.session_state.user_info = user_info
                except:
                    st.session_state.user_info = {'name': 'User', 'email': 'unknown@example.com'}
                
                # Clear query parameters
                st.experimental_set_query_params()
                
                return token_data
                
            except Exception as e:
                st.error(f"❌ OAuth callback error: {str(e)}")
                return None
        
        return None
    
    def authenticate_user(self):
        """Handle Google OAuth authentication with manual implementation"""
        
        # Check for OAuth callback first
        callback_token = self.handle_oauth_callback()
        if callback_token:
            st.success("✅ Successfully logged in!")
            st.experimental_rerun()
        
        # Check if user is already authenticated
        if 'auth_token' in st.session_state:
            return st.session_state.auth_token
        
        # Show login interface
        st.markdown("### 🔐 Login dengan Google untuk mengakses Drive")
        st.info("Klik tombol di bawah untuk login dan memberikan akses ke Google Drive Anda")
        
        # Generate authorization URL
        auth_url = self.get_authorization_url()
        
        # Custom OAuth button
        st.markdown(f"""
        <div style="text-align: center; margin: 2rem 0;">
            <a href="{auth_url}" target="_self" style="
                display: inline-block;
                background: #4285f4;
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: bold;
                font-size: 16px;
                border: none;
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            ">
                🔐 Login dengan Google
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        **Catatan:** 
        - Anda akan diarahkan ke halaman Google untuk login
        - Setelah login, Anda akan kembali ke aplikasi ini
        - Aplikasi hanya meminta akses read-only ke Google Drive Anda
        """)
        
        return None
    
    def build_service(self, token):
        """Build Google Drive service with token"""
        try:
            oauth_config = self.setup_oauth_config()
            
            creds = Credentials(
                token=token['access_token'],
                refresh_token=token.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=oauth_config['client_id'],
                client_secret=oauth_config['client_secret'],
                scopes=self.scopes
            )
            
            # Refresh token if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Update session with new token
                st.session_state.auth_token['access_token'] = creds.token
            
            self.service = build('drive', 'v3', credentials=creds)
            return True
            
        except Exception as e:
            st.error(f"❌ Error building service: {str(e)}")
            # Clear invalid token
            if 'auth_token' in st.session_state:
                del st.session_state.auth_token
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
            with st.expander("📝 Lihat Konten Text", expanded=True):
                st.text_area(
                    "Konten:", 
                    content_data['content'], 
                    height=300,
                    key=f"text_{content_data['id']}"
                )
            
            # Word frequency analysis
            if len(content_data['content']) > 100:
                with st.expander("📊 Analisis Kata"):
                    words = [word.lower().strip('.,!?";()[]{}') for word in content_data['content'].split() 
                            if len(word) > 3 and word.isalpha()]
                    if words:
                        word_freq = pd.Series(words).value_counts().head(10)
                        
                        fig = px.bar(
                            x=word_freq.values,
                            y=word_freq.index,
                            orientation='h',
                            title="Top 10 Kata Paling Sering",
                            labels={'x': 'Frekuensi', 'y': 'Kata'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
        
        # DataFrame content (Excel, CSV)
        elif isinstance(content_data['content'], pd.DataFrame):
            with st.expander("📊 Data Preview", expanded=True):
                st.dataframe(content_data['content'], use_container_width=True)
            
            # Basic statistics for numeric columns
            numeric_cols = content_data['content'].select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) > 0:
                with st.expander("📈 Statistik Dasar"):
                    st.dataframe(content_data['content'][numeric_cols].describe())
                
                # Simple visualization
                if len(numeric_cols) >= 2:
                    st.subheader("📊 Visualisasi Data")
                    col1, col2 = st.columns(2)
                    with col1:
                        x_col = st.selectbox("X-axis", numeric_cols, key=f"x_{content_data['id']}")
                    with col2:
                        y_col = st.selectbox("Y-axis", numeric_cols, key=f"y_{content_data['id']}")
                    
                    if x_col and y_col and x_col != y_col:
                        fig = px.scatter(
                            content_data['content'], 
                            x=x_col, 
                            y=y_col,
                            title=f"{x_col} vs {y_col}"
                        )
                        st.plotly_chart(fig, use_container_width=True)
        
        # List content (CSV rows)
        elif isinstance(content_data['content'], list):
            if content_data['content']:
                with st.expander("📋 Data Table", expanded=True):
                    df = pd.DataFrame(content_data['content'])
                    st.dataframe(df, use_container_width=True)
            else:
                st.info("📄 File kosong")
        
        # JSON content
        elif isinstance(content_data['content'], dict):
            with st.expander("🔍 JSON Content", expanded=True):
                st.json(content_data['content'])
    
    st.divider()

def main():
    """Main Streamlit app"""
    
    # Page config
    st.set_page_config(
        page_title="Google Drive Reader",
        page_icon="📁",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #4285f4, #34a853, #fbbc05, #ea4335);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stButton > button {
        background: linear-gradient(90deg, #4285f4, #34a853);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: bold;
    }
    .oauth-button {
        background: #4285f4 !important;
        color: white !important;
        padding: 12px 24px !important;
        border-radius: 8px !important;
        text-decoration: none !important;
        font-weight: bold !important;
        display: inline-block !important;
        margin: 1rem 0 !important;
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
        st.info("""
        **🔐 Langkah untuk menggunakan aplikasi ini:**
        
        1. Klik tombol "Login dengan Google" di atas
        2. Pilih akun Google Anda
        3. Berikan izin akses ke Google Drive (read-only)
        4. Anda akan diarahkan kembali ke aplikasi
        
        **🔒 Keamanan:**
        - Aplikasi hanya meminta akses read-only
        - Tidak ada data yang disimpan di server
        - Anda dapat mencabut akses kapan saja di Google Account Settings
        """)
        st.stop()
    
    # Build service
    if not reader.build_service(token):
        st.error("❌ Gagal terhubung ke Google Drive. Silakan login ulang.")
        if st.button("🔄 Login Ulang"):
            for key in ['auth_token', 'user_info', 'oauth_state']:
                if key in st.session_state:
                    del st.session_state[key]
            st.experimental_rerun()
        st.stop()
    
    # User info in sidebar
    if 'user_info' in st.session_state:
        user_info = st.session_state.user_info
        with st.sidebar:
            st.success(f"👋 Hello, {user_info.get('name', 'User')}!")
            st.write(f"📧 {user_info.get('email', '')}")
            
            if st.button("🚪 Logout", type="secondary"):
                for key in ['auth_token', 'user_info', 'oauth_state']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.experimental_rerun()
    
    # Main interface
    st.sidebar.header("⚙️ Pengaturan")
    
    # Mode selection
    mode = st.sidebar.radio(
        "Pilih mode:",
        ["📁 Baca Folder", "📄 Baca Single File"],
        help="Pilih apakah ingin membaca seluruh folder atau file individual"
    )
    
    if mode == "📁 Baca Folder":
        st.header("📁 Baca Folder Google Drive")
        
        folder_url = st.text_input(
            "🔗 URL Folder Google Drive:",
            placeholder="https://drive.google.com/drive/folders/1a2b3c4d5e6f...",
            help="Copy URL folder dari address bar browser saat membuka folder di Google Drive"
        )
        
        if st.button("🚀 Baca Folder", type="primary"):
            if folder_url.strip():
                try:
                    with st.spinner("📂 Menganalisis folder..."):
                        folder_id = reader.get_folder_id_from_url(folder_url)
                        files = reader.list_files_in_folder(folder_id)
                    
                    if files:
                        st.success(f"✅ Ditemukan {len(files)} file dalam folder")
                        
                        # Filter options
                        st.sidebar.subheader("🔍 Filter File")
                        file_types = list(set([f['mimeType'] for f in files]))
                        readable_types = []
                        for ft in file_types:
                            if 'google-apps' in ft:
                                readable_types.append(ft.split('.')[-1].title())
                            else:
                                readable_types.append(ft.split('/')[-1].upper())
                        
                        type_mapping = dict(zip(readable_types, file_types))
                        
                        selected_readable = st.sidebar.multiselect(
                            "Pilih tipe file:",
                            readable_types,
                            default=readable_types,
                            help="Filter file berdasarkan tipe yang ingin dibaca"
                        )
                        
                        selected_types = [type_mapping[rt] for rt in selected_readable]
                        
                        # Filter files
                        filtered_files = [f for f in files if f['mimeType'] in selected_types]
                        
                        if filtered_files:
                            # Show file list
                            with st.expander(f"📋 Daftar File ({len(filtered_files)} file)", expanded=False):
                                for i, file in enumerate(filtered_files, 1):
                                    file_type = file['mimeType'].split('/')[-1]
                                    st.write(f"{i}. **{file['name']}** ({file_type})")
                            
                            # Processing options
                            process_all = st.checkbox(
                                "📖 Baca semua file sekaligus", 
                                value=True,
                                help="Uncheck jika hanya ingin melihat daftar file"
                            )
                            
                            if process_all:
                                # Progress bar
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                                
                                # Read files
                                results = []
                                for i, file in enumerate(filtered_files):
                                    if file['mimeType'] != 'application/vnd.google-apps.folder':
                                        status_text.text(f"📖 Membaca: {file['name']} ({i+1}/{len(filtered_files)})")
                                        content = reader.read_file_content(file)
                                        results.append(content)
                                        progress_bar.progress((i + 1) / len(filtered_files))
                                
                                status_text.text("✅ Selesai membaca semua file!")
                                progress_bar.empty()
                                
                                # Display results
                                if results:
                                    st.header(f"📊 Hasil Pembacaan ({len(results)} files)")
                                    
                                    # Summary statistics
                                    successful = len([r for r in results if r['content'] and not r['error']])
                                    failed = len(results) - successful
                                    
                                    col1, col2, col3 = st.columns(3)
                                    col1.metric("✅ Berhasil", successful)
                                    col2.metric("❌ Gagal", failed)
                                    col3.metric("📊 Total", len(results))
                                    
                                    # Display each file
                                    for content_data in results:
                                        display_file_content(content_data)
                        else:
                            st.warning("🔍 Tidak ada file dengan tipe yang dipilih")
                        
                    else:
                        st.warning("📁 Folder kosong atau tidak dapat diakses. Pastikan folder dapat diakses secara public atau Anda memiliki izin akses.")
                        
                except ValueError as ve:
                    st.error(f"❌ {str(ve)}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
            else:
                st.warning("⚠️ Masukkan URL folder terlebih dahulu")
    
    else:  # Single file mode
        st.header("📄 Baca Single File")
        
        file_url = st.text_input(
            "🔗 URL File Google Drive:",
            placeholder="https://drive.google.com/file/d/1a2b3c4d5e6f.../view",
            help="Copy URL file dari address bar browser saat membuka file di Google Drive"
        )
        
        if st.button("📖 Baca File", type="primary"):
            if file_url.strip():
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
                    
                except ValueError as ve:
                    st.error(f"❌ {str(ve)}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
            else:
                st.warning("⚠️ Masukkan URL file terlebih dahulu")
    
    # Footer information
    with st.sidebar:
        st.markdown("---")
        st.markdown("""
        **📋 Format yang didukung:**
        - 📝 Google Docs → Text
        - 📊 Google Sheets → CSV/Table
        - 📄 PDF → Extracted text
        - 📄 Word (.docx) → Text
        - 📊 Excel (.xlsx) → Table
        - 📝 Text files → Raw text
        - 📊 CSV → Table
        - 🔧 JSON → Structured data
        
        **🔒 Privasi & Keamanan:**
        - Akses read-only saja
        - Data tidak disimpan di server
        - Koneksi aman via HTTPS
        - Anda dapat revoke akses kapan saja
        
        **💡 Tips Penggunaan:**
        - File harus dapat diakses oleh akun Google Anda
        - Untuk file besar, proses mungkin memakan waktu
        - Gunakan filter untuk membatasi jenis file
        """)

if __name__ == "__main__":
    main()
