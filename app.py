import streamlit as st
from core.terminal import get_node_manager
from core.ai_pilot import AIPilot
from core.vault import CommandVault
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="AI Terminal Pilot", layout="wide")

# Initialize modules
node_manager = get_node_manager()
pilot = AIPilot()
vault = CommandVault()

st.title("🎮 Remote AI Terminal Pilot")

# Refresh the page every 500ms to pull new terminal output and telemetry
st_autorefresh(interval=500, key="terminal_update")

# Sidebar: Node Selection & Command Vault
with st.sidebar:
    st.header("🖥️ System Nodes")
    nodes = node_manager.list_nodes()

    # Auto-select the first node if the active one somehow disappears
    current_index = 0
    if node_manager.active_node_name in nodes:
        current_index = nodes.index(node_manager.active_node_name)

    selected_node = st.selectbox("Active Computer:", nodes, index=current_index)
    node_manager.active_node_name = selected_node

    with st.expander("➕ Manual Connect"):
        new_node_name = st.text_input("Node Name (e.g. Server-01)")
        new_node_ip = st.text_input("IP Address")
        if st.button("Connect"):
            if new_node_name and new_node_ip:
                node_manager.add_remote_node(new_node_name, new_node_ip)
                st.success(f"Connecting to {new_node_name}...")
                st.rerun()

    st.write("---")
    st.header("📢 Global Control")
    broadcast_cmd = st.text_input("Broadcast Command:")
    if st.button("🚀 Send to All Nodes"):
        node_manager.broadcast(broadcast_cmd)
        st.warning("Command sent to all active nodes.")

    st.write("---")
    st.header("📂 Command Vault")
    if st.button("Save Last Command"):
        # Logic can be expanded to save current st.session_state.suggestion
        pass
    st.write("---")
    saved = vault.get_all()
    for _, name, cmd, _ in saved:
        if st.button(f"📦 {name}"):
            node_manager.get_active_node().execute(cmd)

# Main Terminal Interface
terminal = node_manager.get_active_node()

# TOP SECTION: Telemetry Dashboard
stats = terminal.get_telemetry()
cols = st.columns(3)
cols[0].metric("CPU Usage", f"{stats['cpu']}%")
cols[1].metric("RAM Usage", f"{stats['ram']}%")
cols[2].metric("Disk Usage", f"{stats['disk']}%")

st.write("---")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("🤖 AI Session")
    mode = st.radio("Pilot Mode", ["Manual (Review)", "Auto (Agentic)"])
    user_query = st.text_input("What do you want to do?")
    
    if st.button("Generate"):
        suggestion = pilot.suggest_command(user_query)
        st.session_state.suggestion = suggestion
        
    if "suggestion" in st.session_state:
        st.code(st.session_state.suggestion, language="powershell")
        if mode == "Manual (Review)":
            if st.button("Run Command"):
                terminal.execute(st.session_state.suggestion)
        else:
            terminal.execute(st.session_state.suggestion)

with col1:
    st.subheader(f"💻 Live Terminal: {node_manager.active_node_name}")

    # Simple input for manual commands
    with st.form("cmd_form", clear_on_submit=True):
        cmd_input = st.text_input("Command:")
        submit = st.form_submit_button("Execute")
        if submit and cmd_input:
            terminal.execute(cmd_input)
    
    # Real-time output container
    output_container = st.empty()
    if "terminal_log" not in st.session_state:
        st.session_state.terminal_log = ""
    
    new_output = terminal.get_new_output()
    if new_output:
        st.session_state.terminal_log += new_output
    
    output_container.code(st.session_state.terminal_log, language="text")

    if st.button("Clear Log"):
        st.session_state.terminal_log = ""
        st.rerun()
