"""
main.py
Main entry point for StructDB application
"""

import tkinter as tk
import sys
import os

def main():
    """Main function to start the application"""
    try:
        # Add current directory to Python path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        print("=" * 60)
        print("Starting StructDB - Professional Database Engine")
        print("=" * 60)
        
    
        print("Loading modules...")
        import gui
        
        
        print("Creating application window...")
        root = tk.Tk()
        
        
        print("Initializing GUI...")
        app = gui.StructDBGUI(root)
        
        print("✓ StructDB started successfully!")
        print("=" * 60)
        
        
        root.mainloop()
        
    except ImportError as ie:
        print(f"\n✗ ERROR: Failed to import required module")
        print(f"Details: {ie}")
        print("\nMake sure all .py files are in the same directory:")
        print("  - main.py")
        print("  - gui.py")
        print("  - database_manager.py")
        print("  - database.py")
        print("  - query_parser.py")
        print("  - data_structures.py")
        input("\nPress Enter to exit...")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")


if __name__ == '__main__':
    main()