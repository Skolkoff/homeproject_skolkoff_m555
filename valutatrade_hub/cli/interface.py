def main() -> None:
    print("ValutaTrade Hub. Type 'help' for commands or 'exit' to quit.")
    while True:
        try:
            command = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return
        if command == "exit":
            print("Goodbye!")
            return
        if command == "help":
            print("Available commands: help, exit")
