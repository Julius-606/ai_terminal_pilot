import streamlit as st
from core.terminal import get_node_manager
from core.ai_pilot import AIPilot
from core.vault import CommandVault
from streamlit_autorefresh import st_autorefresh
import time
import os

st.set_page_config(page_title="AI Terminal Pilot", layout="wide", initial_sidebar_state="expanded")

# --- Custom Styling ---
st.markdown("""
    <style>
    .stCode {
        background-color: #0e1117;
    }
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
    }
    .chat-bubble {
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .user-bubble {
        background-color: #262730;
    }
    .ai-bubble {
        background-color: #1e2130;
        border-left: 5px solid #ff4b4b;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Initialization ---
node_manager = get_node_manager()
pilot = AIPilot()
vault = CommandVault()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "terminal_log" not in st.session_state:
    st.session_state.terminal_log = ""
if "suggestion" not in st.session_state:
    st.session_state.suggestion = None

st_autorefresh(interval=1000, key="global_refresh")

# --- Sidebar ---
with st.sidebar:
    st.title("🎮 Pilot Center")

    st.header("🖥️ System Nodes")
    nodes = node_manager.list_nodes()
    selected_node = st.selectbox("Active Node:", nodes, index=nodes.index(node_manager.active_node_name))
    node_manager.active_node_name = selected_node

    st.write("---")
    st.header("📂 Command Vault")
    saved_commands = vault.get_all()
    if not saved_commands:
        st.info("No commands saved yet.")
    else:
        for cmd_id, name, cmd, cat in saved_commands:
            col_a, col_b = st.columns([4, 1])
            if col_a.button(f"🚀 {name}", key=f"vault_{cmd_id}", use_container_width=True, help=cmd):
                node_manager.get_active_node().execute(cmd)
            if col_b.button("🗑️", key=f"del_{cmd_id}"):
                # Add delete logic to vault.py later if needed
                pass

    st.write("---")
    st.header("📢 Broadcast")
    b_cmd = st.text_input("Execute on ALL nodes:")
    if st.button("Global Execute"):
        node_manager.broadcast(b_cmd)
        st.success("Broadcasted!")

# --- Main Dashboard ---
terminal = node_manager.get_active_node()
stats = terminal.get_telemetry()

# Header Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Node", selected_node)
m2.metric("CPU", f"{stats['cpu']}%")
m3.metric("RAM", f"{stats['ram']}%")
m4.metric("Disk", f"{stats['disk']}%")

st.divider()

# Layout: Terminal (Left) | AI Agent (Right)
col_term, col_ai = st.columns([1.2, 1])

with col_term:
    st.subheader(f"💻 Live Terminal")
    
    # Terminal Output
    new_output = terminal.get_new_output()
    if new_output:
        st.session_state.terminal_log += new_output
    
    st.code(st.session_state.terminal_log if st.session_state.terminal_log else "Terminal initialized...", language="text")

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("Clear Console", use_container_width=True):
        st.session_state.terminal_log = ""
        st.rerun()

    # Manual Input
    with st.form("manual_cmd", clear_on_submit=True):
        shell_name = "PowerShell" if os.name == "nt" else "Shell"
        cmd_in = st.text_input(f"Enter {shell_name} Command:")
        if st.form_submit_button("Run"):
            terminal.execute(cmd_in)

with col_ai:
    st.subheader("🤖 AI Agentic Pilot")

    if not pilot.api_keys:
        st.warning("AI is not configured. Add GEMINI_API_KEY to your .env file and restart the app.")

    # Chat Display
    chat_container = st.container(height=400)
    for message in st.session_state.chat_history:
        role = message["role"]
        with chat_container:
            with st.chat_message("user" if role == "user" else "assistant"):
                st.markdown(message["content"], unsafe_allow_html=True)

    # Input area
    user_input = st.chat_input("Ask the pilot to do something...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # Analyze current terminal context for the AI
        context = st.session_state.terminal_log[-2000:] # Last 2000 chars

        with st.spinner("AI Thinking..."):
            suggestion_data = pilot.suggest_command(user_input, context=context)
            st.session_state.suggestion = suggestion_data
            
            # Extract content for chat history
            cmd = suggestion_data.get("command", "")
            expl = suggestion_data.get("explanation", "")
            st.session_state.chat_history.append({
                "role": "ai", 
                "content": f"{expl}<br><br><b>Command:</b> `{cmd}`"
            })
        st.rerun()

    # Suggested Action Card
    if st.session_state.suggestion:
        suggestion = st.session_state.suggestion
        st.info(f"### ⚡ Suggested Command\n{suggestion.get('explanation', '')}")
        st.code(suggestion.get("command", ""), language="powershell")

        c1, c2, c3 = st.columns(3)
        if c1.button("✅ Execute", use_container_width=True):
            terminal.execute(suggestion.get("command", ""))
            st.session_state.suggestion = None
            st.rerun()

        if c2.button("💾 Save to Vault", use_container_width=True):
            vault.save_command(
                f"AI: {suggestion.get('explanation', '')[:20]}...", 
                suggestion.get("command", "")
            )
            st.toast("Command saved to vault!")

        if c3.button("❌ Dismiss", use_container_width=True):
            st.session_state.suggestion = None
            st.rerun()
