import os
import gradio as gr
from core.ai_pilot import AIPilot
from core.terminal import get_node_manager
from core.vault import CommandVault

node_manager = get_node_manager()
pilot = AIPilot()
vault = CommandVault()


def refresh_metrics():
    terminal = node_manager.get_active_node()
    stats = terminal.get_telemetry()
    return (
        node_manager.active_node_name,
        f"{stats['cpu']}%",
        f"{stats['ram']}%",
        f"{stats['disk']}%",
    )


def get_terminal_output_text(log_text):
    terminal = node_manager.get_active_node()
    new_output = terminal.get_new_output()
    if new_output:
        log_text = (log_text or "") + new_output
    return log_text if log_text else "Terminal initialized..."


def handle_ai_request(message, history, log_text):
    if not message or not message.strip():
        return history, log_text, None, ""

    updated_history = history or []
    updated_history.append({"role": "user", "content": message})
    context = (log_text or "")[-2000:]
    suggestion = pilot.suggest_command(message, context=context)
    command = suggestion.get("command", "")
    explanation = suggestion.get("explanation", "")
    response = f"{explanation}\n\n**Command:** `{command}`"
    updated_history.append({"role": "assistant", "content": response})
    return updated_history, log_text, suggestion, response


def run_manual_command(command, log_text):
    if command and command.strip():
        node_manager.get_active_node().execute(command)
    return log_text


def clear_console():
    return "", "Terminal initialized..."


def broadcast_command(command):
    if command and command.strip():
        node_manager.broadcast(command)
        return "Broadcasted!"
    return "No command entered."


def save_suggestion_to_vault(suggestion):
    if not suggestion:
        return "No suggestion available."
    vault.save_command(
        f"AI: {suggestion.get('explanation', '')[:20]}...",
        suggestion.get("command", "")
    )
    return "Command saved to vault."


def execute_suggestion_command(suggestion, log_text):
    if suggestion:
        command = suggestion.get("command", "")
        if command:
            node_manager.get_active_node().execute(command)
    return log_text, "", None


theme = getattr(gr.themes, "Dark", None)
if theme is None:
    theme = getattr(gr.themes, "Soft", None)
if theme is None:
    theme = getattr(gr.themes, "Default", None)
if theme is not None:
    theme = theme()

with gr.Blocks() as demo:
    gr.Markdown("# 🎮 AI Terminal Pilot")

    state_chat = gr.State([])
    state_terminal = gr.State("")
    state_suggestion = gr.State(None)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## 🧭 Pilot Center")
            node_dropdown = gr.Dropdown(
                choices=node_manager.list_nodes(),
                value=node_manager.active_node_name,
                label="Active Node",
            )
            global_command = gr.Textbox(label="Execute on all nodes", placeholder="Command to broadcast")
            global_execute = gr.Button("Global Execute")
            global_status = gr.Markdown("")

            gr.Markdown("## 📂 Command Vault")
            saved_commands = vault.get_all()
            if saved_commands:
                for cmd_id, name, cmd, _ in saved_commands:
                    cmd_button = gr.Button(f"🚀 {name}", variant="secondary")
                    cmd_button.click(
                        run_manual_command,
                        inputs=[gr.State(cmd), state_terminal],
                        outputs=[state_terminal],
                    )
            else:
                gr.Markdown("No commands saved yet.")

        with gr.Column(scale=3):
            with gr.Row():
                node_display = gr.Textbox(label="Node", value=node_manager.active_node_name, interactive=False)
                cpu_display = gr.Textbox(label="CPU", value="0%", interactive=False)
                ram_display = gr.Textbox(label="RAM", value="0%", interactive=False)
                disk_display = gr.Textbox(label="Disk", value="0%", interactive=False)

            gr.Markdown("## 💻 Live Terminal")
            terminal_output = gr.Textbox(
                label="Terminal Output",
                value="Terminal initialized...",
                lines=18,
                max_lines=18,
            )

            with gr.Row():
                manual_command = gr.Textbox(label="Command", placeholder="Enter a PowerShell command")
                run_command = gr.Button("Run")
                clear_button = gr.Button("Clear Console")

            gr.Markdown("## 🤖 AI Agentic Pilot")
            chatbot = gr.Chatbot(value=[], height=420)
            prompt = gr.Textbox(label="Ask the pilot to do something...", placeholder="Ask the pilot to do something...")
            send_prompt = gr.Button("Send")
            suggestion_box = gr.Markdown("")
            suggestion_code = gr.Code(value="", language="shell", label="Suggested command")
            with gr.Row():
                execute_offer = gr.Button("✅ Execute")
                save_offer = gr.Button("💾 Save to Vault")
                dismiss_offer = gr.Button("❌ Dismiss")

    def node_changed(node_name, log_text):
        node_manager.active_node_name = node_name
        name, cpu, ram, disk = refresh_metrics()
        updated_log = get_terminal_output_text(log_text)
        return name, cpu, ram, disk, updated_log, updated_log

    def timer_tick(log_text):
        terminal = node_manager.get_active_node()
        new_output = terminal.get_new_output()
        updated_log = log_text or ""
        if new_output:
            updated_log += new_output
        name, cpu, ram, disk = refresh_metrics()
        return name, cpu, ram, disk, updated_log, (updated_log if updated_log else "Terminal initialized...")

    def update_suggestion_display(suggestion):
        if not suggestion:
            return "", ""
        command = suggestion.get("command", "")
        explanation = suggestion.get("explanation", "")
        return f"### ⚡ Suggested Command\n{explanation}", command

    node_dropdown.change(
        node_changed,
        inputs=[node_dropdown, state_terminal],
        outputs=[node_display, cpu_display, ram_display, disk_display, state_terminal, terminal_output],
    )
    timer = gr.Timer(1)
    timer.tick(
        timer_tick,
        inputs=[state_terminal],
        outputs=[node_display, cpu_display, ram_display, disk_display, state_terminal, terminal_output],
    )

    run_command.click(run_manual_command, inputs=[manual_command, state_terminal], outputs=[state_terminal])
    clear_button.click(clear_console, inputs=None, outputs=[state_terminal, terminal_output])
    global_execute.click(broadcast_command, inputs=global_command, outputs=[global_status])

    send_prompt.click(handle_ai_request, inputs=[prompt, state_chat, state_terminal], outputs=[state_chat, state_terminal, state_suggestion, suggestion_box])
    prompt.submit(handle_ai_request, inputs=[prompt, state_chat, state_terminal], outputs=[state_chat, state_terminal, state_suggestion, suggestion_box])

    state_chat.change(lambda history: history, inputs=state_chat, outputs=[chatbot])
    state_suggestion.change(update_suggestion_display, inputs=state_suggestion, outputs=[suggestion_box, suggestion_code])

    save_offer.click(save_suggestion_to_vault, inputs=state_suggestion, outputs=[global_status])
    execute_offer.click(
        execute_suggestion_command,
        inputs=[state_suggestion, state_terminal],
        outputs=[state_terminal, suggestion_code, state_suggestion],
    )
    dismiss_offer.click(lambda: (None, ""), outputs=[state_suggestion, suggestion_code])


def main():
    port = int(os.getenv("PORT", "7860"))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        debug=False,
        theme=theme,
        css="""
            .gradio-container { max-width: 1500px; }
            .terminal-output textarea { font-family: monospace; }
        """,
    )


if __name__ == "__main__":
    main()

