#!/usr/bin/env python3
# Borderlands 4 Lost Loot Item Injector
# Leverages functions from blcrypt.py for encryption/decryption.

import sys
from pathlib import Path
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --- Import Mandatory Libraries (Needed before blcrypt check) ---
# Import blcrypt functions, and fail gracefully with a GUI message if not found
try:
    from blcrypt import decrypt_sav_to_yaml, encrypt_yaml_to_sav
except ImportError:
    # If the import fails, show a GUI error message and then exit the script entirely.
    root = tk.Tk()
    root.withdraw() # Hide the main window that pops up temporarily
    messagebox.showerror(
        "Fatal Error: Missing File", 
        "FATAL ERROR: Could not find 'blcrypt.py'. Please ensure 'blcrypt.py' is in the same directory as this injector script."
    )
    sys.exit(1)


# --- Persistence Files ---
# Store the last-used SteamID in a hidden file in the script's directory.
STEAM_ID_FILE = Path(__file__).parent / ".last_steam_id"
# Store the last-used directory path for browsing files
LAST_PATH_FILE = Path(__file__).parent / ".last_browse_path"

# --- Borderlands Save Game Path Components (Windows Default) ---
# Target path structure: Documents\My Games\Borderlands 4\Saved\SaveGames\SteamID\Profiles\client
SAVE_GAME_BASE_PATH_COMPONENTS = [
    'My Games',
    'Borderlands 4',
    'Saved', 
    'SaveGames'
]


# --- Core Logic Functions ---

def generate_yaml_fragment(codes: list) -> list[str]:
    """
    Generates the correctly formatted YAML lines for the new items.
    Requires 4 spaces for the list item (- serial:) and 6 spaces for the child key (in_machine:).
    """
    yaml_lines = []
    for code in codes:
        # 4 spaces for the list item: must align under 'items:'
        yaml_lines.append(f'    - serial: \'{code.strip()}\'')
        # 6 spaces for the child key: must align under 'serial:' value
        yaml_lines.append(f'      in_machine: true')
    return yaml_lines

def load_serial_codes(codes_path: Path) -> list[str]:
    """Loads and cleans serial codes from a text file."""
    codes = []
    try:
        with codes_path.open('r', encoding='utf-8') as f:
            for line in f:
                code = line.strip()
                # Skip empty lines, comments, and short strings
                if code and not code.startswith('#') and len(code) > 10:
                    codes.append(code)
        return codes
    except Exception as e:
        raise RuntimeError(f"Error reading serial codes file: {e}")

# --- GUI Application Class ---

class LostLootApp:
    def __init__(self, master):
        self.master = master
        master.title("Borderlands 4 Lost Loot Injector")

        # Set up variables
        self.steam_id_var = tk.StringVar(master)
        self.codes_path_var = tk.StringVar(master)
        self.sav_path_var = tk.StringVar(master)
        self.last_path = None # Will store the Path object of the last browsed directory

        # Load last persisted data
        self._load_steam_id()
        self._load_last_path()
        self.steam_id_var.trace_add('write', self._steam_id_changed)

        # --- Define Colors ---
        DARK_BACKGROUND = '#1E1E1E'
        CHARCOAL = '#333333'
        VIOLET = '#9400D3'
        WHITE = '#FFFFFF'
        LIGHT_GRAY = '#CCCCCC'

        # Configure Style
        style = ttk.Style()
        master.configure(bg=DARK_BACKGROUND)
        style.configure('TFrame', background=DARK_BACKGROUND)
        style.configure('TLabel', background=DARK_BACKGROUND, foreground=LIGHT_GRAY, font=('Arial', 10))

        # 1. General Button Style (for 'Browse')
        style.configure('TButton', 
            background=CHARCOAL,
            foreground=VIOLET,
            font=('Arial', 10, 'bold'), 
            padding=6,
            borderwidth=0
        )
        style.map('TButton', 
            background=[('active', '#555555')],
        )

        # 2. Accent Button Style (for 'Execute')
        style.configure('Accent.TButton', 
            background=CHARCOAL, 
            foreground=VIOLET, 
            font=('Arial', 12, 'bold'),
            borderwidth=0
        )
        style.map('Accent.TButton', 
            background=[('active', '#555555')], 
            foreground=[('active', VIOLET)] 
        )

        # Main frame
        main_frame = ttk.Frame(master, padding="20 20 20 20")
        main_frame.pack(fill='both', expand=True)

        # 1. Steam ID Input
        self._create_input_row(
            main_frame, "1. Steam ID:", self.steam_id_var, None, 0,
            fg=WHITE # Ensure input field text is white
        )

        # 2. Serial Codes File Input
        self._create_input_row(
            main_frame, "2. Codes File (.txt):", self.codes_path_var, self._browse_codes_file, 1
        )

        # 3. Character Save File Input
        self._create_input_row(
            main_frame, "3. Character Save (.sav):", self.sav_path_var, self._browse_save_file, 2
        )

        # 4. Execute Button
        execute_button = ttk.Button(main_frame, text="Execute Injection (Creates .sav.old Backup)", command=self._execute_injection, style='Accent.TButton')
        execute_button.grid(row=3, column=0, columnspan=3, pady=20, sticky='EW')

        # 5. Status Label
        self.status_var = tk.StringVar(master, value="Ready. Ensure blcrypt.py is in the same directory.")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, wraplength=400, justify=tk.LEFT, font=('Arial', 9, 'italic'))
        status_label.grid(row=4, column=0, columnspan=3, pady=(10, 0), sticky='W')

    def _create_input_row(self, parent, label_text, var, command, row_num, fg='#CCCCCC'):
        """Helper to create a label, entry, and optional button/tooltip for one row."""
        label = ttk.Label(parent, text=label_text)
        label.grid(row=row_num, column=0, padx=5, pady=5, sticky='W')

        # Entry widget with custom colors for the dark theme
        entry = tk.Entry(parent, textvariable=var, width=50, bg='#2D2D2D', fg=fg, insertbackground='white', bd=1, relief=tk.FLAT)
        entry.grid(row=row_num, column=1, padx=5, pady=5, sticky='EW')

        if command:
            browse_button = ttk.Button(parent, text="Browse", command=command, width=8)
            browse_button.grid(row=row_num, column=2, padx=5, pady=5, sticky='E')
            
        parent.grid_columnconfigure(1, weight=1)

    def _get_steam_id_default_dir(self, steam_id: str) -> Path:
        """
        Calculates the default Borderlands 4 save directory path based on SteamID.
        Used as a fallback when no persistent path is saved.
        Path structure: Documents\My Games\Borderlands 4\Saved\SaveGames\SteamID\Profiles\client
        """
        documents_path = Path.home() / 'Documents'
        base_path = documents_path
        
        # Build the path components: Documents/My Games/Borderlands 4/Saved/SaveGames
        for component in SAVE_GAME_BASE_PATH_COMPONENTS:
            base_path /= component

        # Full target path: .../SaveGames/SteamID/Profiles/client
        target_path = base_path / steam_id / 'Profiles' / 'client'
        
        # Check for existence to provide the deepest working initial directory
        if target_path.is_dir():
            return target_path
        
        # Fallback 1: SteamID directory
        steam_id_path = base_path / steam_id
        if steam_id_path.is_dir():
             return steam_id_path

        # Fallback 2: Base Save Games path
        if base_path.is_dir():
            return base_path
            
        # Fallback 3: The Documents folder
        return documents_path

    def _get_initial_dir(self) -> Path:
        """
        Determines the initial directory for the file dialog.
        Prioritizes the last browsed path, falls back to the Steam ID default path.
        """
        if self.last_path and self.last_path.is_dir():
            return self.last_path
        
        steam_id = self.steam_id_var.get().strip()
        if steam_id.isdigit() and len(steam_id) >= 17:
            return self._get_steam_id_default_dir(steam_id)
            
        return Path.home() # Absolute last resort

    def _load_steam_id(self):
        """Loads the last-used Steam ID from the persistence file."""
        if STEAM_ID_FILE.exists():
            try:
                steam_id = STEAM_ID_FILE.read_text().strip()
                if steam_id.isdigit():
                    self.steam_id_var.set(steam_id)
            except Exception:
                pass # Ignore errors

    def _save_steam_id(self, steam_id):
        """Saves the current Steam ID to the persistence file."""
        if steam_id.isdigit() and len(steam_id) >= 17:
            try:
                STEAM_ID_FILE.write_text(steam_id)
            except Exception:
                pass # Ignore errors

    def _load_last_path(self):
        """Loads the last-used browse path from the persistence file."""
        if LAST_PATH_FILE.exists():
            try:
                last_path_str = LAST_PATH_FILE.read_text().strip()
                last_path = Path(last_path_str)
                if last_path.is_dir():
                    self.last_path = last_path
            except Exception:
                pass # Ignore errors

    def _save_last_path(self, file_path: Path):
        """Saves the directory of the selected file to the persistence file."""
        try:
            # We save the parent directory, as this is the folder the user browsed into
            LAST_PATH_FILE.write_text(str(file_path.parent))
            self.last_path = file_path.parent
        except Exception:
            pass # Ignore errors

    def _steam_id_changed(self, *args):
        """Called when the Steam ID input changes."""
        self._save_steam_id(self.steam_id_var.get())

    def _browse_codes_file(self):
        """Opens dialog to select the serial codes text file."""
        
        initial_dir = self._get_initial_dir()
        
        filename = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Select Serial Codes File (.txt)",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filename:
            file_path = Path(filename)
            self.codes_path_var.set(str(file_path))
            self._save_last_path(file_path) # Save the directory for next time

    def _browse_save_file(self):
        """Opens dialog to select the character save file."""
        steam_id = self.steam_id_var.get().strip()
        if not steam_id.isdigit() or len(steam_id) < 17:
            messagebox.showwarning("Input Required", "Please enter a valid 17-digit Steam ID first.")
            return

        initial_dir = self._get_initial_dir()

        filename = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Select Character Save File (.sav)",
            filetypes=[("Borderlands Save Files", "*.sav"), ("All Files", "*.*")]
        )
        if filename:
            file_path = Path(filename)
            self.sav_path_var.set(str(file_path))
            self._save_last_path(file_path) # Save the directory for next time

    def _execute_injection(self):
        """Main execution logic, including backup and overwrite."""
        steam_id = self.steam_id_var.get().strip()
        sav_in_path = Path(self.sav_path_var.get().strip())
        codes_path = Path(self.codes_path_var.get().strip())

        # 1. Validation
        if not (steam_id and steam_id.isdigit() and len(steam_id) >= 17):
            messagebox.showerror("Error", "Invalid Steam ID. Please ensure it is the full 17-digit number.")
            return
        if not sav_in_path.exists() or sav_in_path.suffix.lower() != '.sav':
            messagebox.showerror("Error", "Invalid or missing character save file (.sav).")
            return
        if not codes_path.exists() or codes_path.suffix.lower() != '.txt':
            messagebox.showerror("Error", "Invalid or missing serial codes file (.txt).")
            return

        self.status_var.set("Starting injection process...")
        self.master.update() # Force GUI refresh

        temp_yaml_path = None
        try:
            # Load codes
            codes_to_inject = load_serial_codes(codes_path)
            if not codes_to_inject:
                messagebox.showwarning("Warning", "The codes file is empty or contains no valid serial codes.")
                return

            new_item_lines = generate_yaml_fragment(codes_to_inject)

            # Define paths
            sav_original_path = sav_in_path
            sav_backup_path = sav_in_path.with_suffix(".sav.old")
            # Create a unique temporary file path for the YAML to avoid conflicts
            temp_yaml_path = sav_in_path.with_suffix(".temp_lost_loot.yaml")

            # 2. Backup Original File
            self.status_var.set(f"Creating backup: {sav_backup_path.name}...")
            shutil.copy(sav_original_path, sav_backup_path)

            # 3. Decrypt the .sav file
            self.status_var.set("Decrypting save file...")
            yaml_bytes = decrypt_sav_to_yaml(sav_original_path, steam_id)
            yaml_text = yaml_bytes.decode('utf-8')
            yaml_lines = yaml_text.splitlines()

            # 4. Find the correct insertion point
            self.status_var.set("Finding Lost Loot insertion point...")

            lost_loot_index = -1
            for i, line in enumerate(yaml_lines):
                if line.strip().startswith('lostloot:'):
                    lost_loot_index = i
                    break
                    
            if lost_loot_index == -1:
                raise RuntimeError("Could not find the 'lostloot:' section in the save file. This save might be corrupt or incompatible.")

            items_list_index = -1
            for i in range(lost_loot_index, len(yaml_lines)):
                if yaml_lines[i].strip() == 'items:':
                    items_list_index = i
                    break
                    
            if items_list_index == -1:
                # If 'items:' isn't found, we inject it right after 'lostloot:'
                insertion_point = lost_loot_index + 1
                new_item_lines.insert(0, '  items:')
                
            else:
                # Standard case: items: found. We insert after the last existing item.
                insertion_point = items_list_index + 1

                # Search for the last line of an existing item block: 'in_machine: true'
                for i in range(items_list_index + 1, len(yaml_lines)):
                    line = yaml_lines[i]
                    
                    if line.startswith('      in_machine:'):
                        insertion_point = i + 1
                    
                    # Check for end of lostloot block by indentation dropping below the item list indentation (2 spaces)
                    elif line.strip() and len(line) - len(line.lstrip()) <= 2:
                        break
            
            # 5. Inject the new lines
            self.status_var.set(f"Injecting {len(codes_to_inject)} new item serial codes...")
            modified_yaml_lines = yaml_lines[:insertion_point] + new_item_lines + yaml_lines[insertion_point:]
            modified_yaml_text = "\n".join(modified_yaml_lines)
            
            # 6. Encrypt and Overwrite Original File
            self.status_var.set("Encrypting and overwriting original save file...")
            
            # Write the modified content to the temporary file
            temp_yaml_path.write_text(modified_yaml_text, encoding='utf-8')
            
            # Encrypt
            sav_bytes = encrypt_yaml_to_sav(temp_yaml_path, steam_id)
            
            # Overwrite the original save file with the new data
            sav_original_path.write_bytes(sav_bytes)
            
            self.status_var.set(f"SUCCESS! {len(codes_to_inject)} items injected into Lost Loot machine.")
            messagebox.showinfo("Success", f"Successfully injected {len(codes_to_inject)} items into:\n{sav_original_path.name}\n\nBackup created at:\n{sav_backup_path.name}")

        except RuntimeError as e:
            self.status_var.set(f"ERROR: {e}")
            messagebox.showerror("Runtime Error", f"An error occurred during processing:\n{e}")
        except Exception as e:
            self.status_var.set(f"FATAL ERROR: {type(e).__name__}: {e}")
            messagebox.showerror("Fatal Error", f"A fatal error occurred:\n{type(e).__name__}: {e}")
            
        finally:
            # Cleanup temporary file
            if temp_yaml_path and temp_yaml_path.exists():
                os.remove(temp_yaml_path)

def main():
    # Clean up the console pause/exit functions if they were imported from blcrypt
    if 'blcrypt' in sys.modules and 'pause_and_exit' in sys.modules['blcrypt'].__dict__:
        if hasattr(sys.modules['blcrypt'], 'pause_and_exit'):
            del sys.modules['blcrypt'].pause_and_exit
        
    try:
        root = tk.Tk()
        app = LostLootApp(root)
        root.mainloop()
    except Exception as e:
        # Show message box for startup error as a last resort
        try:
            temp_root = tk.Tk()
            temp_root.withdraw()
            messagebox.showerror("Startup Error", f"An unexpected error occurred during GUI startup:\n{type(e).__name__}: {e}")
        except:
            print(f"Error during GUI startup: {e}")
            
if __name__ == "__main__":
    main()
