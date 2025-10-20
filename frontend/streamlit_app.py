import streamlit as st
import requests
import time
from datetime import datetime
import re

st.set_page_config(
    page_title="AgroSense",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_BASE_URL = "http://127.0.0.1:8000"
CHAT_ENDPOINT = f"{API_BASE_URL}/api/v1/chat"
STATUS_ENDPOINT = f"{API_BASE_URL}/api/v1/status"
WEATHER_ENDPOINT = f"{API_BASE_URL}/api/v1/weather"

st.markdown("""
    <style>
        /* Main App Background */
        .stApp { background: #333333 !important; }
        .main { background: #333333 !important; }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px; background: transparent !important; }

        /* Header */
        .main-header {
            background: #075e54;
            padding: 1.25rem 2rem;
            border-radius: 0;
            margin: -1rem -1rem 1rem -1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .main-header h1 { color: #ffffff; margin: 0; font-size: 1.75rem; font-weight: 500; }
        .main-header p { color: #d9fdd3; margin: 0.25rem 0 0 0; font-size: 0.9rem; }

        /* Sidebar */
        section[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #d1d7db; }
        section[data-testid="stSidebar"] > div { background: #ffffff !important; }
        section[data-testid="stSidebar"] .stMarkdown h3 { color: #075e54 !important; font-size: 1.1rem !important; font-weight: 600 !important; margin-bottom: 1rem !important; margin-top: 1rem !important; }
        section[data-testid="stSidebar"] .stMarkdown p, section[data-testid="stSidebar"] .stMarkdown div, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] .stMarkdown { color: #3b4a54 !important; }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #3b4a54 !important; }

        /* Weather Card */
        .weather-card { background: linear-gradient(135deg, #128c7e 0%, #075e54 100%); padding: 1.25rem; border-radius: 12px; color: #ffffff; margin: 1rem 0; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
        .weather-card h4 { margin: 0 0 0.75rem 0; font-size: 1rem; font-weight: 600; color: #ffffff; }
        .weather-metric { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.2); color: #ffffff; }
        .weather-metric:last-child { border-bottom: none; }
        .weather-metric span { color: #ffffff; }

        /* Info Box */
        .info-box { background: #d9fdd3 !important; border-left: 4px solid #25d366 !important; padding: 1rem !important; border-radius: 8px !important; margin: 1rem 0 !important; }
        .info-box, .info-box * { color: #3b4a54 !important; line-height: 1.6 !important; }
        .info-box strong { color: #075e54 !important; display: block; margin-bottom: 0.5rem; font-weight: 600; }

        /* Status Badges */
        .status-badge { display: inline-block; padding: 0.4rem 0.9rem; border-radius: 16px; font-size: 0.8rem; font-weight: 600; margin: 0.25rem 0.25rem 0.75rem 0; }
        .badge-processing { background: #fff4e5 !important; color: #8b5a00 !important; border: 1px solid #ffb84d !important; }
        .badge-completed { background: #d4edda !important; color: #155724 !important; border: 1px solid #28a745 !important; }
        .badge-crop { background: #e8f5e9 !important; color: #1b5e20 !important; border: 1px solid #4caf50 !important; }
        .badge-livestock { background: #fff3e0 !important; color: #e65100 !important; border: 1px solid #ff9800 !important; }
        .badge-general { background: #e3f2fd !important; color: #0d47a1 !important; border: 1px solid #2196f3 !important; }

        /* Alert Box */
        .alert-critical { background: #f8d7da !important; border-left: 4px solid #dc3545 !important; padding: 1rem !important; border-radius: 8px !important; margin: 1rem 0 !important; }
        .alert-critical, .alert-critical * { color: #721c24 !important; font-weight: 500 !important; }

        /* Buttons */
        .stButton > button { background: #25d366 !important; color: #ffffff !important; border: none !important; border-radius: 8px !important; padding: 0.6rem 1.5rem !important; font-weight: 600 !important; transition: all 0.2s !important; width: 100% !important; }
        .stButton > button:hover { background: #20ba5a !important; transform: translateY(-1px) !important; box-shadow: 0 4px 12px rgba(37, 211, 102, 0.3) !important; }
        .stDownloadButton > button { background: #128c7e !important; color: #ffffff !important; border: none !important; border-radius: 8px !important; padding: 0.6rem 1.5rem !important; font-weight: 600 !important; width: 100% !important; }
        .stDownloadButton > button:hover { background: #0c7268 !important; }

        /* Chat Container */
        [data-testid="stChatMessageContainer"] { background: #000000 !important; padding: 1rem !important; }

        /* Chat Messages */
        .stChatMessage { padding: 0.75rem 1rem !important; margin: 0.5rem 0 !important; border-radius: 8px !important; max-width: 75% !important; box-shadow: 0 1px 2px rgba(0,0,0,0.15) !important; }

        /* User Messages (Green) */
        .stChatMessage[data-testid="stChatMessage-user"] { background: #d9fdd3 !important; margin-left: auto !important; margin-right: 0 !important; border: none !important; }
        .stChatMessage[data-testid="stChatMessage-user"] *, .stChatMessage[data-testid="stChatMessage-user"] p, .stChatMessage[data-testid="stChatMessage-user"] span, .stChatMessage[data-testid="stChatMessage-user"] div { color: #303030 !important; background-color: transparent !important; }

        /* Assistant Messages (White) */
        .stChatMessage[data-testid="stChatMessage-assistant"] { background: #ffffff !important; margin-left: 0 !important; margin-right: auto !important; border: none !important; }
        .stChatMessage[data-testid="stChatMessage-assistant"] *, .stChatMessage[data-testid="stChatMessage-assistant"] p, .stChatMessage[data-testid="stChatMessage-assistant"] span, .stChatMessage[data-testid="stChatMessage-assistant"] div, .stChatMessage[data-testid="stChatMessage-assistant"] h1, .stChatMessage[data-testid="stChatMessage-assistant"] h2, .stChatMessage[data-testid="stChatMessage-assistant"] h3, .stChatMessage[data-testid="stChatMessage-assistant"] h4, .stChatMessage[data-testid="stChatMessage-assistant"] li, .stChatMessage[data-testid="stChatMessage-assistant"] strong, .stChatMessage[data-testid="stChatMessage-assistant"] code, .stChatMessage[data-testid="stChatMessage-assistant"] [data-testid="stMarkdownContainer"], .stChatMessage[data-testid="stChatMessage-assistant"] [data-testid="stMarkdownContainer"] * { color: #1a1a1a !important; background-color: transparent !important; }

        /* Ensure headings in diagnosis are visible */
        .stChatMessage[data-testid="stChatMessage-assistant"] h2 { color: #075e54 !important; font-weight: 600 !important; margin-top: 1rem !important; margin-bottom: 0.5rem !important; }

        /* Captions (Timestamps) */
        .stChatMessage [data-testid="stCaptionContainer"], .stChatMessage [data-testid="stCaptionContainer"] *, .stChatMessage .stCaption, .stChatMessage .stCaption * { color: #667781 !important; font-size: 0.7rem !important; margin-top: 0.25rem !important; }

        /* Chat Input */
        .stChatInput { background: #f0f2f5 !important; border-radius: 24px !important; padding: 0.5rem !important; }
        .stChatInput textarea { border-radius: 24px !important; border: none !important; background: #ffffff !important; padding: 12px 20px !important; color: #3b4a54 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important; }
        .stChatInput textarea:focus { border: 2px solid #25d366 !important; box-shadow: 0 0 0 3px rgba(37, 211, 102, 0.1) !important; outline: none !important; }
        .stChatInput textarea::placeholder { color: #8696a0 !important; }

        /* Empty State */
        .empty-state { text-align: center; padding: 3rem 1.5rem; background: #ffffff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); max-width: 600px; margin: 2rem auto; }
        .empty-state-icon { font-size: 4rem; margin-bottom: 1rem; }
        .empty-state h3 { color: #075e54 !important; font-weight: 600 !important; margin-bottom: 0.5rem; }
        .empty-state p { color: #667781 !important; font-size: 0.95rem; }

        /* Selectbox */
        .stSelectbox label { color: #3b4a54 !important; font-weight: 500 !important; }

        /* Success/Info/Warning Messages */
        .stSuccess { background: #d4edda !important; color: #155724 !important; border-left: 4px solid #28a745 !important; }
        .stInfo { background: #d1ecf1 !important; color: #0c5460 !important; border-left: 4px solid #17a2b8 !important; }
        .stWarning { background: #fff3cd !important; color: #856404 !important; border-left: 4px solid #ffc107 !important; }
        .stError { background: #f8d7da !important; color: #721c24 !important; border-left: 4px solid #dc3545 !important; }

        /* Avatar styling */
        .stChatMessage img { width: 36px !important; height: 36px !important; border-radius: 50% !important; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------
# Session State
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "diagnosis_status" not in st.session_state:
    st.session_state.diagnosis_status = None
if "last_diagnosis" not in st.session_state:
    st.session_state.last_diagnosis = None
if "region" not in st.session_state:
    st.session_state.region = "Nairobi"

# -----------------------------
# Header
# -----------------------------
st.markdown("""
    <div class="main-header">
        <h1>🌾 AgroSense</h1>
        <p>Your intelligent farming companion for Kenya</p>
    </div>
""", unsafe_allow_html=True)

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    regions = [
        "Nairobi", "Mombasa", "Nakuru", "Eldoret", "Kisumu",
        "Thika", "Malindi", "Nyeri", "Meru", "Kitale",
        "Kakamega", "Machakos", "Bungoma", "Embu"
    ]
    region = st.selectbox("📍 Select Region", regions, index=regions.index(st.session_state.region))
    st.session_state.region = region

    st.markdown("---")
    st.markdown("### 🌤️ Weather Info")
    try:
        weather_resp = requests.get(f"{WEATHER_ENDPOINT}?region={region}", timeout=5)
        if weather_resp.status_code == 200:
            data = weather_resp.json()
            st.markdown(f"""
                <div class="weather-card">
                    <h4>🌤️ {region} Weather</h4>
                    <div class="weather-metric">
                        <span>🌡️ Temperature</span>
                        <span style="font-weight: 600;">{data.get('temperature', 'N/A')}°C</span>
                    </div>
                    <div class="weather-metric">
                        <span>💧 Humidity</span>
                        <span style="font-weight: 600;">{data.get('humidity', 'N/A')}%</span>
                    </div>
                    <div class="weather-metric">
                        <span>☁️ Condition</span>
                        <span style="font-weight: 600;">{data.get('condition', 'Unknown')}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            market = data.get('market_price', 'N/A')
            if market != 'N/A':
                st.markdown("**💰 Market Price**")
                st.caption(market)
        else:
            st.warning("⚠️ Weather unavailable")
    except Exception:
        st.error("❌ Weather service error")

    st.markdown("---")
    st.markdown("### 💬 Session")
    if st.session_state.session_id:
        st.success("🟢 Active")
        st.caption(f"ID: {st.session_state.session_id[:12]}...")
        st.caption(f"Messages: {len(st.session_state.messages)}")
        if st.session_state.diagnosis_status == "processing":
            st.info("🔄 Analyzing...")
        elif st.session_state.diagnosis_status == "completed":
            st.success("✅ Ready!")
    else:
        st.info("💬 Start chatting")

    st.markdown("---")
    if st.session_state.last_diagnosis:
        st.markdown("### 📥 Download")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        download_content = f"""
═══════════════════════════════════════════
        AGROSENSE DIAGNOSIS REPORT
═══════════════════════════════════════════

📅 Date: {timestamp}
📍 Region: {st.session_state.region}
🆔 Session: {st.session_state.session_id[:16] if st.session_state.session_id else 'N/A'}

═══════════════════════════════════════════
            DIAGNOSIS & RECOMMENDATIONS
═══════════════════════════════════════════

{st.session_state.last_diagnosis}

═══════════════════════════════════════════
Generated by AgroSense AI
🌾 Your intelligent farming companion
🌍 Made for Kenya
═══════════════════════════════════════════
"""
        filename = f"agrosense_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        st.download_button(label="📄 Download Report", data=download_content, file_name=filename, mime="text/plain", use_container_width=True)
        st.caption("Complete diagnosis with recommendations")
        st.markdown("---")

    st.markdown("### ⚡ Actions")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 New", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = None
            st.session_state.processing = False
            st.session_state.diagnosis_status = None
            st.session_state.last_diagnosis = None
            st.rerun()
    with col2:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_diagnosis = None
            st.rerun()

    st.markdown("---")
    st.markdown("### 💡 How to Use")
    st.markdown("""
    <div class="info-box">
        <strong>Getting Started:</strong>
        1️⃣ Describe your farming issue<br>
        2️⃣ Mention your location<br>
        3️⃣ Share symptoms/details<br>
        4️⃣ Get expert diagnosis!
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
        <div style="padding: 0.5rem 0; color: #667781; font-size: 0.85rem; text-align: center;">
            🌿 Powered by CrewAI<br>
            🤖 Multi-Agent System<br>
            🇰🇪 Made for Kenya
        </div>
    """, unsafe_allow_html=True)

# -----------------------------
# Chat Area Rendering
# -----------------------------
if len(st.session_state.messages) == 0:
    st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">👨‍🌾</div>
            <h3>Welcome to AgroSense!</h3>
            <p>I'm here to help with all your farming questions.</p>
            <p style="margin-top: 1.5rem; font-size: 0.9rem; color: #8696a0;">
                <strong>Try asking:</strong><br>
                "My maize has white spots"<br>
                "When should I plant potatoes?"<br>
                "Best fertilizer for tomatoes?"
            </p>
        </div>
    """, unsafe_allow_html=True)
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="👨‍🌾" if msg["role"] == "user" else "🤖"):
            if msg["role"] == "assistant" and msg.get("classification"):
                cls = msg["classification"]
                asset_type = cls.get("asset_type", "GENERAL").lower()
                st.markdown(f"""
                    <div style="margin-bottom: 0.75rem;">
                        <span class="status-badge badge-{asset_type}">🌱 {cls.get('asset_type', 'N/A')}</span>
                        <span class="status-badge badge-general">📦 {cls.get('asset_name', 'N/A')}</span>
                        <span class="status-badge badge-general">🎯 {cls.get('intent', 'N/A')}</span>
                    </div>
                """, unsafe_allow_html=True)

            if msg["role"] == "assistant" and msg.get("requires_action"):
                st.markdown('<span class="status-badge badge-processing">🔄 Analysis Started</span>', unsafe_allow_html=True)

            if msg["role"] == "assistant" and msg.get("is_diagnosis"):
                st.markdown('<span class="status-badge badge-completed">✅ Complete Diagnosis</span>', unsafe_allow_html=True)

            if msg["role"] == "assistant" and msg.get("alert_triggered"):
                severity = msg.get("alert_severity", "UNKNOWN")
                st.markdown(f"""
                    <div class="alert-critical">
                        🚨 <strong>CRITICAL ALERT: {severity}</strong><br>
                        This condition requires immediate attention!
                    </div>
                """, unsafe_allow_html=True)

            st.markdown(msg["content"])
            if msg.get("timestamp"):
                st.caption(f"🕐 {msg['timestamp']}")

# -----------------------------
# Input
# -----------------------------
user_input = st.chat_input("Type your message...", disabled=st.session_state.processing)

if user_input and not st.session_state.processing:
    # Push user message to session state
    timestamp = datetime.now().strftime("%I:%M %p")
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": timestamp
    })

    # Prepare payload for backend
    payload = {
        "message": user_input,
        "session_id": st.session_state.session_id,
        "farmer_id": f"farmer_{st.session_state.region.lower()}"
    }

    # Set processing flags
    st.session_state.processing = True
    st.session_state.diagnosis_status = None

    # Show explicit status (keeps UI responsive)
    status_placeholder = st.empty()
    status_placeholder.info("🤖 AgroSense is thinking...")

    try:
        # Send initial chat request
        response = requests.post(CHAT_ENDPOINT, json=payload, timeout=120)

        if response.status_code == 200:
            data = response.json()
            # Use the 'message' field (this contains the full diagnosis text or initial assistant reply)
            assistant_message = data.get("message", "")
            st.session_state.session_id = data.get("session_id", st.session_state.session_id)

            msg_data = {
                "role": "assistant",
                "content": assistant_message,
                "timestamp": datetime.now().strftime("%I:%M %p"),
                "requires_action": data.get("requires_action", False),
                "classification": data.get("classification"),
                "alert_triggered": data.get("alert_triggered", False),
                "alert_severity": data.get("alert_severity")
            }
            st.session_state.messages.append(msg_data)

            # If the backend signals that a diagnosis background job has started, poll status endpoint
            if data.get("requires_action"):
                st.session_state.diagnosis_status = "processing"
                # visible progress using st.status() context
                with st.status("🔍 Analyzing request and consulting experts...", expanded=True, state="running") as status_bar:
                    max_polls = 40
                    for attempt in range(max_polls):
                        time.sleep(3)
                        status_bar.update(label=f"🔄 Processing diagnosis... (Attempt {attempt+1}/{max_polls})", state="running")

                        try:
                            status_resp = requests.get(f"{STATUS_ENDPOINT}/{st.session_state.session_id}", timeout=10)
                        except Exception as ex:
                            # If it's the last attempt, append a timeout message
                            if attempt == max_polls - 1:
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": "⏱️ Analysis is taking longer than expected. Please check back later or start a new conversation.",
                                    "timestamp": datetime.now().strftime("%I:%M %p")
                                })
                                status_bar.update(label="⏱️ Analysis Timed Out", state="error", expanded=False)
                                st.session_state.diagnosis_status = "failed"
                                break
                            continue

                        if status_resp.status_code != 200:
                            # treat as still processing; continue polling
                            if attempt == max_polls - 1:
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": "⏱️ Analysis is taking longer than expected. Please check back later or start a new conversation.",
                                    "timestamp": datetime.now().strftime("%I:%M %p")
                                })
                                status_bar.update(label="⏱️ Analysis Timed Out", state="error", expanded=False)
                                st.session_state.diagnosis_status = "failed"
                                break
                            continue

                        status_data = status_resp.json()
                        status = status_data.get("status", "processing")

                        if status == "completed":
                            st.session_state.diagnosis_status = "completed"
                            # server-side diagnosis might be in status_data['diagnosis']
                            diagnosis_text = status_data.get("diagnosis", "")
                            # If diagnosis_text is absent, fallback to message or stored
                            if not diagnosis_text:
                                diagnosis_text = status_data.get("message", "") or assistant_message

                            # --- CLEANING LOGIC (keep full content, remove trailing JSON metadata/code blocks) ---
                            # Remove code blocks (```...```)
                            diagnosis_text = re.sub(r'```.*?```', '', diagnosis_text, flags=re.DOTALL).strip()

                            # Remove trailing small JSON metadata objects like {"alert_triggered": ... , "reason":"..."}
                            json_metadata_pattern = r'\s*\{\s*"alert_triggered"\s*:\s*(?:true|false|null)\s*,\s*"reason"\s*:\s*".*?"\s*(?:,\s*".*?":\s*.*?)*\}\s*$'
                            if re.search(json_metadata_pattern, diagnosis_text, flags=re.DOTALL):
                                # If the entire response is just that JSON, keep it as fallback (don't drop everything)
                                # If it's part of a longer text, remove it from the end
                                if len(diagnosis_text) > 200:  # heuristic: if response long, remove metadata
                                    diagnosis_text = re.sub(json_metadata_pattern, '', diagnosis_text, flags=re.DOTALL).strip()

                            # Remove extraneous brackets/braces at begin/end
                            diagnosis_text = diagnosis_text.strip('{}[]\n ')

                            # Normalize repeated blank lines
                            diagnosis_text = re.sub(r'\n{3,}', '\n\n', diagnosis_text).strip()

                            if diagnosis_text:
                                st.session_state.last_diagnosis = diagnosis_text
                            else:
                                st.session_state.last_diagnosis = status_data.get("diagnosis", assistant_message)

                            # Append diagnosis message to chat
                            diag_msg = {
                                "role": "assistant",
                                "content": st.session_state.last_diagnosis,
                                "timestamp": datetime.now().strftime("%I:%M %p"),
                                "is_diagnosis": True,
                                "classification": status_data.get("classification"),
                                "alert_triggered": status_data.get("alert_triggered", False),
                                "alert_severity": status_data.get("alert_severity")
                            }
                            st.session_state.messages.append(diag_msg)

                            status_bar.update(label="✅ Analysis Complete!", state="complete", expanded=False)
                            break  # exit polling loop

                        elif status == "failed":
                            st.session_state.diagnosis_status = "failed"
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": "❌ Analysis failed. Please try again with more details.",
                                "timestamp": datetime.now().strftime("%I:%M %p")
                            })
                            status_bar.update(label="❌ Analysis Failed", state="error", expanded=False)
                            break
                        # else: still processing -> continue loop

                    # End of polling loop
                    if st.session_state.diagnosis_status == "processing":
                        # timed out
                        status_bar.update(label="⏱️ Analysis Timed Out", state="error", expanded=False)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "⏱️ Analysis is taking longer than expected. Please check back later or start a new conversation.",
                            "timestamp": datetime.now().strftime("%I:%M %p")
                        })
                        st.session_state.diagnosis_status = "failed"

            # End requires_action handling

        else:
            # Non-200 from initial call
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"⚠️ Error: Unable to process request (Status: {response.status_code})",
                "timestamp": datetime.now().strftime("%I:%M %p")
            })

    except requests.exceptions.Timeout:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⏱️ Request timed out. Please try again.",
            "timestamp": datetime.now().strftime("%I:%M %p")
        })
    except requests.exceptions.ConnectionError:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "🔌 Cannot connect to server. Make sure the API is running at http://127.0.0.1:8000",
            "timestamp": datetime.now().strftime("%I:%M %p")
        })
    except Exception as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"❌ Error: {str(e)}",
            "timestamp": datetime.now().strftime("%I:%M %p")
        })
    finally:
        # Ensure processing flag cleared and UI updated
        st.session_state.processing = False
        try:
            status_placeholder.empty()
        except Exception:
            pass
        st.rerun()
