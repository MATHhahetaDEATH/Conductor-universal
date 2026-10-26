from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.patch_stdout import patch_stdout
import logging

from conductor.core.kernel import Kernel
from conductor.core.permission import CommandSource, PermissionLevel

class ConsoleSource(CommandSource):
    def __init__(self):
        super().__init__("Console", PermissionLevel.OWNER)
        self.logger = logging.getLogger("conductor.console")

    def reply(self, message: str, plugin_id: str = "core") -> None:
        if plugin_id == "core":
            self.logger.info(message)
        else:
            logging.getLogger(f"conductor.plugins.{plugin_id}").info(message)

class ConductorCompleter(Completer):
    def __init__(self, kernel: Kernel):
        self.kernel = kernel
        
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        suggestions = self.kernel.generate_suggestions(text)
        
        # We need to yield Completion objects. 
        # document.get_word_before_cursor() usually splits by space
        word = document.get_word_before_cursor(WORD=True)
        
        for suggestion in suggestions:
            # We suggest the entire word but offset by the characters already typed
            if suggestion.startswith(word):
                yield Completion(suggestion, start_position=-len(word))

def cli_loop(kernel: Kernel):
    """Background thread to read and execute commands using prompt_toolkit."""
    source = ConsoleSource()
    completer = ConductorCompleter(kernel)
    session = PromptSession(completer=completer)
    
    print("Conductor CLI Ready. Type !!help for commands.")
    
    while not kernel.shutdown_event.is_set():
        try:
            with patch_stdout():
                # This will wait for user input, supporting tab completion
                text = session.prompt("> ").strip()
            
            if text:
                kernel.execute_command(source, text)
        except KeyboardInterrupt:
            # Exit loop on Ctrl+C
            print("\nInterrupt received, shutting down...")
            break
        except EOFError:
            # Handle Ctrl+D
            break
        except Exception as e:
            if not kernel.shutdown_event.is_set():
                print(f"CLI Error: {e}")
