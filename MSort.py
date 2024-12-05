import os
import re
import json
import sys
import requests
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import ttk
from threading import Thread

CACHE_FILE = "mod_cache.json"


def get_mod_title(mod_id, cache):
    if mod_id in cache:
        return cache[mod_id]

    url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("div", {"class": "workshopItemTitle"})
        if title_tag:
            cache[mod_id] = title_tag.text.strip()
            return cache[mod_id]
    return "Unknown Title"


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            return json.load(file)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as file:
        json.dump(cache, file, indent=4)


def parse_workshop_file(file_path):
    with open(file_path, "r") as file:
        return re.findall(r'"(\d+)"\s+"(\d)"', file.read())


def save_workshop_file(file_path, mod_list):
    with open(file_path, "w") as file:
        file.write('"AddonInfo"\n{\n')
        file.writelines(f'    "{mod_id}"    "{state}"\n' for mod_id, state in mod_list)
        file.write('}\n')


def truncate_title(title, max_length=45):
    return title if len(title) <= max_length else title[:max_length] + "..."


class ModSorterApp(tk.Tk):
    def __init__(self, workshop_path, mods, cache):
        super().__init__()
        self.title("JokeDeity's Jank Workshop Mod Sorter")
        self.geometry("1000x1080")
        self.configure(bg="#000000")

        self.workshop_path = workshop_path
        self.mods = mods
        self.cache = cache
        self.selected_items = []  # For multi-selection during drag

        self.create_widgets()
        self.populate_treeview()

    def create_widgets(self):
        self.frame = ttk.Frame(self)
        self.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.treeview = ttk.Treeview(
            self.frame,
            columns=("ID", "Name", "State"),
            show="headings",
            selectmode="extended",
            height=25,
        )
        self.treeview.heading("ID", text="ID")
        self.treeview.heading("Name", text="Name")
        self.treeview.heading("State", text="State")
        self.treeview.column("ID", width=100, anchor="w")
        self.treeview.column("Name", width=400, anchor="center")
        self.treeview.column("State", width=100, anchor="center")  # Centering the State column

        # Apply dark background and light font color to treeview items
        self.treeview.tag_configure("dark", background="#2a2a2a", foreground="#ffffff")
        
        self.scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.treeview.yview)
        self.treeview.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.treeview.bind("<ButtonPress-1>", self.start_drag)
        self.treeview.bind("<B1-Motion>", self.drag)
        self.treeview.bind("<ButtonRelease-1>", self.end_drag)
        self.treeview.bind("<Double-1>", self.toggle_state)

        self.save_button = ttk.Button(self, text="Save Order", command=self.save_order)
        self.save_button.pack(pady=10)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", background="#444444", foreground="#ffffff", font=("Consolas", 10), padding=5)
        style.map("TButton", background=[("active", "#666666")])
        style.configure(
            "TScrollbar",
            gripcount=0,
            background="#444444",
            darkcolor="#222222",
            lightcolor="#444444",
            troughcolor="#2a2a2a",
        )

    def populate_treeview(self):
        for index, (mod_id, state) in enumerate(self.mods):
            title = self.cache.get(mod_id, "Loading...")
            self.treeview.insert(
                "", tk.END, values=(mod_id, truncate_title(title), state), tags=("dark",)
            )
            Thread(target=self.update_mod_title, args=(index, mod_id), daemon=True).start()

    def update_mod_title(self, index, mod_id):
        title = get_mod_title(mod_id, self.cache)
        save_cache(self.cache)
        self.after(0, self.update_treeview_item, index, mod_id, title)

    def update_treeview_item(self, index, mod_id, title):
        state = self.mods[index][1]
        item = self.treeview.get_children()[index]
        self.treeview.item(item, values=(mod_id, truncate_title(title), state))

    def start_drag(self, event):
        region = self.treeview.identify_region(event.x, event.y)
        if region == "cell":
            self.selected_items = self.treeview.selection()

    def drag(self, event):
        """Handles the dragging of selected items."""
        target_item = self.treeview.identify_row(event.y)

        if not target_item or target_item in self.selected_items:
            return

        target_index = self.treeview.index(target_item)
        items_to_move = [self.treeview.item(item)["values"] for item in self.selected_items]

        for item in self.selected_items:
            self.treeview.delete(item)

        for i, values in enumerate(items_to_move):
            self.treeview.insert("", target_index + i, values=values)

        self.selected_items = [
            self.treeview.get_children()[target_index + i] for i in range(len(items_to_move))
        ]

    def end_drag(self, event):
        self.selected_items = []

    def toggle_state(self, event):
        item = self.treeview.identify_row(event.y)
        if item:
            mod_id, title, state = self.treeview.item(item, "values")
            new_state = "0" if state == "1" else "1"
            self.treeview.item(item, values=(mod_id, title, new_state))
            index = self.treeview.index(item)
            self.mods[index] = (mod_id, new_state)

    def save_order(self):
        reordered = []
        for item in self.treeview.get_children():
            mod_id, title, state = self.treeview.item(item, "values")
            reordered.append((mod_id, state))
        save_workshop_file(self.workshop_path, reordered)
        save_cache(self.cache)
        print("Order saved to workshop.txt")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    workshop_path = os.path.join(base_dir, "workshop.txt")

    if os.path.exists(workshop_path):
        cache = load_cache()
        mods = parse_workshop_file(workshop_path)
        app = ModSorterApp(workshop_path, mods, cache)
        app.mainloop()
    else:
        print(f"{workshop_path} not found!")
