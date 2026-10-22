"""Tk interface for filtered Eru player statistics."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk

from modules.main.eruAnalysis import Condition, EruAnalysisService, Filters, condition_expression, eru_list


class EruAnalysisPanel:
    def __init__(self, host, frame, project_root, categories):
        self.host, self.frame = host, frame
        self.service = EruAnalysisService(project_root)
        self.mode_options = {
            f"{category} - {label}": tour_id
            for category, entries in categories.items() if category != "Eru"
            for label, tour_id in entries
        }
        self.mode = tk.StringVar(host)
        self.start_year = tk.StringVar(host)
        self.end_year = tk.StringVar(host)
        self.status = tk.StringVar(host, value="No data loaded.")
        self.search = tk.StringVar(host)
        self.conditions = []
        self.condition_link = tk.StringVar(host, value="OR")
        self.expression = tk.StringVar(host, value="All songs")
        self.tags, self.genres = set(), set()
        self.totals = None
        self.busy = False
        self.events = queue.Queue()
        self.sort_column, self.sort_reverse = "rate", True
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)

        filters = ttk.Frame(frame)
        filters.grid(row=0, column=0, sticky="ew")
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text="Tour type *").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.mode_combo = ttk.Combobox(filters, textvariable=self.mode, values=tuple(self.mode_options), state="readonly", width=24)
        self.mode_combo.grid(row=0, column=1, sticky="ew", padx=(0, 16))
        ttk.Label(filters, text="Release year").grid(row=0, column=2, padx=(0, 8))
        self.start_entry = ttk.Entry(filters, textvariable=self.start_year, width=7)
        self.start_entry.grid(row=0, column=3)
        ttk.Label(filters, text="to").grid(row=0, column=4, padx=8)
        self.end_entry = ttk.Entry(filters, textvariable=self.end_year, width=7)
        self.end_entry.grid(row=0, column=5)

        criteria = ttk.Frame(frame)
        criteria.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        self.genres_button = ttk.Button(criteria, text="Genres", command=lambda: self.choose_values("genres"))
        self.genres_button.pack(side="left", padx=(0, 8))
        self.tags_button = ttk.Button(criteria, text="Tags", command=lambda: self.choose_values("tags"))
        self.tags_button.pack(side="left")

        builder = ttk.Frame(frame)
        builder.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        builder.columnconfigure(0, weight=1)
        ttk.Label(builder, text="Conditions").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.condition_table = ttk.Treeview(builder, columns=("link", "type", "value"), show="headings", selectmode="browse", height=3)
        self.condition_table.grid(row=1, column=0, sticky="ew")
        for column, title, width in (("link", "Link", 65), ("type", "Type", 70), ("value", "Genre / Tag", 300)):
            self.condition_table.heading(column, text=title)
            self.condition_table.column(column, width=width, minwidth=50, stretch=column == "value")
        condition_scroll = ttk.Scrollbar(builder, orient="vertical", command=self.condition_table.yview)
        condition_scroll.grid(row=1, column=1, sticky="ns")
        self.condition_table.configure(yscrollcommand=condition_scroll.set)
        editor = ttk.Frame(builder)
        editor.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 6))
        ttk.Label(editor, text="Link Operator").pack(side="left", padx=(0, 8))
        self.link_combo = ttk.Combobox(editor, textvariable=self.condition_link, values=("AND", "OR"), width=6, state="disabled")
        self.link_combo.pack(side="left", padx=(0, 8))
        self.link_combo.bind("<<ComboboxSelected>>", self.change_condition_link)
        self.condition_up = ttk.Button(editor, text="Move Up", command=lambda: self.move_condition(-1))
        self.condition_up.pack(side="left", padx=(0, 8))
        self.condition_down = ttk.Button(editor, text="Move Down", command=lambda: self.move_condition(1))
        self.condition_down.pack(side="left", padx=(0, 8))
        self.condition_remove = ttk.Button(editor, text="Remove", command=self.remove_condition)
        self.condition_remove.pack(side="left")
        self.condition_table.bind("<<TreeviewSelect>>", self.select_condition)
        ttk.Entry(builder, textvariable=self.expression, state="readonly").grid(row=3, column=0, columnspan=2, sticky="ew")
        self.select_condition()

        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, sticky="ew")
        self.calculate_button = ttk.Button(actions, text="Calculate", command=self.run_calculation)
        self.calculate_button.pack(side="left", padx=(0, 8))
        self.copy_button = ttk.Button(actions, text="Copy Eru List", command=self.copy_dialog, state="disabled")
        self.copy_button.pack(side="left")
        ttk.Entry(actions, textvariable=self.search, width=18).pack(side="right")
        ttk.Label(actions, text="Search").pack(side="right", padx=(8, 8))
        status_label = ttk.Label(frame, textvariable=self.status, wraplength=680)
        status_label.grid(row=4, column=0, sticky="ew", pady=(6, 6))
        status_label.bind("<Configure>", lambda event: status_label.configure(wraplength=max(200, event.width)))

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=5, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, columns=("player", "encounters", "correct", "rate"), show="headings", selectmode="browse")
        self.table.grid(row=0, column=0, sticky="nsew")
        for column, title, width in (("player", "Player", 240), ("encounters", "Encounters", 115), ("correct", "Correct", 100), ("rate", "GR (%)", 100)):
            self.table.heading(column, text=title, command=lambda c=column: self.sort_by(c))
            self.table.column(column, width=width, minwidth=80, anchor="w" if column == "player" else "e", stretch=column == "player")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)
        for variable in (self.mode, self.start_year, self.end_year):
            variable.trace_add("write", self.invalidate)
        self.search.trace_add("write", lambda *_args: self.show_results())

    def selected_condition(self):
        selected = self.condition_table.selection()
        return int(selected[0]) if selected else None

    def select_condition(self, _event=None):
        index = self.selected_condition()
        enabled = index is not None and not self.busy
        self.link_combo.configure(state="readonly" if enabled and index > 0 else "disabled")
        self.condition_link.set(self.conditions[index].link if index is not None and index > 0 else "")
        self.condition_up.configure(state="normal" if enabled and index > 0 else "disabled")
        self.condition_down.configure(state="normal" if enabled and index < len(self.conditions) - 1 else "disabled")
        self.condition_remove.configure(state="normal" if enabled else "disabled")

    def update_conditions(self, conditions, selected=None):
        self.conditions = list(conditions)
        self.tags = {item.value for item in conditions if item.field == "tags"}
        self.genres = {item.value for item in conditions if item.field == "genres"}
        self.condition_table.delete(*self.condition_table.get_children())
        for index, item in enumerate(conditions):
            self.condition_table.insert("", "end", iid=str(index), values=(item.link if index else "Start", "Genre" if item.field == "genres" else "Tag", item.value))
        if conditions:
            index = min(selected if selected is not None else len(conditions) - 1, len(conditions) - 1)
            self.condition_table.selection_set(str(index))
            self.condition_table.see(str(index))
        self.expression.set(condition_expression(conditions))
        self.select_condition()
        self.invalidate()

    def change_condition_link(self, _event=None):
        index = self.selected_condition()
        if not self.busy and index is not None and index > 0:
            conditions = list(self.conditions)
            conditions[index] = replace(conditions[index], link=self.condition_link.get())
            self.update_conditions(conditions, index)

    def move_condition(self, direction):
        index = self.selected_condition()
        if self.busy or index is None or not 0 <= index + direction < len(self.conditions):
            return
        conditions = list(self.conditions)
        # Links belong to the gaps between rows, not the terms being moved.
        target = index + direction
        first, second = conditions[index], conditions[target]
        conditions[index] = replace(second, link=first.link)
        conditions[target] = replace(first, link=second.link)
        self.update_conditions(conditions, target)

    def remove_condition(self):
        index = self.selected_condition()
        if self.busy or index is None:
            return
        conditions = list(self.conditions)
        conditions.pop(index)
        self.update_conditions(conditions, index)

    def invalidate(self, *_args):
        self.totals = None
        self.copy_button.configure(state="disabled")
        self.table.delete(*self.table.get_children())
        if not self.busy:
            self.status.set("Filters changed. Calculation required.")

    def filters(self):
        try:
            start = int(self.start_year.get().strip()) if self.start_year.get().strip() else None
            end = int(self.end_year.get().strip()) if self.end_year.get().strip() else None
        except ValueError:
            raise ValueError("Enter a four-digit release year or leave it empty.") from None
        return Filters(self.mode_options.get(self.mode.get(), ""), start_year=start, end_year=end, conditions=tuple(self.conditions))

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.calculate_button, self.genres_button, self.tags_button, self.start_entry, self.end_entry):
            widget.configure(state="disabled" if busy else "normal")
        self.mode_combo.configure(state="disabled" if busy else "readonly")
        self.select_condition()
        self.copy_button.configure(state="normal" if not busy and self.totals is not None else "disabled")

    def start_worker(self, operation, finished):
        if self.busy:
            return
        self.invalidate()
        self.set_busy(True)

        def worker():
            try:
                self.events.put(("done", operation()))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))

        def poll():
            try:
                while True:
                    kind, value = self.events.get_nowait()
                    if kind == "progress":
                        self.status.set(value)
                    else:
                        self.set_busy(False)
                        if kind == "error":
                            self.status.set("Could not complete calculation.")
                            messagebox.showerror("Eru Player Stats", value, parent=self.host)
                        else:
                            finished(value)
                        return
            except queue.Empty:
                self.host.after(80, poll)

        threading.Thread(target=worker, daemon=True).start()
        self.host.after(80, poll)

    def warning(self):
        skipped = self.service.skipped_rows
        warning = f" WARNING: {self.service.cache_warning}" if self.service.cache_warning else ""
        if skipped:
            warning += f" WARNING: skipped {len(skipped):,} malformed rows (first: {skipped[0][0]}). Results may be incomplete."
        return warning

    def run_calculation(self):
        try:
            filters = self.filters()
        except ValueError as exc:
            messagebox.showerror("Eru Player Stats", str(exc), parent=self.host)
            return

        def work():
            self.service.load(lambda text: self.events.put(("progress", text)), force=False)
            self.events.put(("progress", "Calculating player encounters..."))
            return self.service.calculate(filters)

        def finished(result):
            self.totals, count, mode_count = result
            self.show_results()
            self.copy_button.configure(state="normal")
            text = f"{len(self.totals):,} players | {count:,} matching songs | {sum(v[0] for v in self.totals.values()):,} player encounters"
            text += f" | {self.service.last_processed_songs:,} songs processed"
            if not mode_count:
                text = "No separately labeled JsonData records for this mode. No other mode's data was substituted."
            self.status.set(text + self.warning())
        self.start_worker(work, finished)

    def show_results(self):
        self.table.delete(*self.table.get_children())
        if self.totals is None:
            return
        search = self.search.get().strip().casefold()
        resolved = self.service.identities.resolve(search) if search else None
        rows = []
        for identity, (count, correct) in self.totals.items():
            name = self.service.identities.names[identity]
            if search and search not in name.casefold() and resolved != identity:
                continue
            rows.append((name, count, correct, 100 * correct / count))
        index = ("player", "encounters", "correct", "rate").index(self.sort_column)
        rows.sort(key=lambda row: row[0].casefold())
        rows.sort(key=lambda row: row[0].casefold() if index == 0 else row[index], reverse=self.sort_reverse)
        for name, count, correct, rate in rows:
            self.table.insert("", "end", values=(name, count, correct, f"{rate:.2f}%"))

    def sort_by(self, column):
        self.sort_reverse = not self.sort_reverse if self.sort_column == column else column != "player"
        self.sort_column = column
        self.show_results()

    def dialog(self, title, geometry):
        dialog = tk.Toplevel(self.host)
        dialog.title(title)
        dialog.configure(bg=self.host.colors["bg"])
        dialog.geometry(geometry)
        dialog.transient(self.host)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        return dialog

    def choose_values(self, field):
        if self.service.songs is None:
            def loaded(count):
                self.status.set(f"Loaded {count:,} song records." + self.warning())
                self.choose_values(field)
            self.start_worker(lambda: self.service.load(lambda text: self.events.put(("progress", text)), force=False), loaded)
            return
        selected = set(getattr(self, field))
        dialog = self.dialog("Select " + field.title(), "440x500")
        dialog.minsize(360, 320)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        search = tk.StringVar(dialog)
        search_entry = ttk.Entry(body, textvariable=search)
        search_entry.pack(fill="x", pady=(0, 8))
        dialog.bind("<Map>", lambda event: search_entry.focus_set() if event.widget == dialog else None, add="+")
        area = ttk.Frame(body)
        area.pack(fill="both", expand=True)
        canvas = tk.Canvas(area, background=self.host.colors["bg"], highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scroll.set)
        choices_frame = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=choices_frame, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        choices_frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        choices = self.service.choices(field)
        variables = {value: tk.BooleanVar(dialog, value=value in selected) for value in choices}

        def scroll_wheel(event):
            if canvas.bbox("all") and choices_frame.winfo_height() > canvas.winfo_height():
                delta = getattr(event, "delta", 0)
                direction = -1 if getattr(event, "num", None) == 4 or delta > 0 else 1
                steps = max(1, abs(delta) // 120)
                canvas.yview_scroll(direction * steps, "units")
            return "break"

        # The toplevel bind tag receives wheel events from every child, including
        # the embedded frame's blank space. Bindings disappear with the popup.
        for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            dialog.bind(event, scroll_wheel)

        def refresh(*_args):
            for child in choices_frame.winfo_children():
                child.destroy()
            for value in choices:
                if search.get().casefold() in value.casefold():
                    check = ttk.Checkbutton(choices_frame, text=value, variable=variables[value])
                    check.pack(anchor="w", pady=2)
            canvas.yview_moveto(0)
        search.trace_add("write", refresh)
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(12, 0))

        def clear():
            for variable in variables.values():
                variable.set(False)

        def apply():
            selected = {value for value, variable in variables.items() if variable.get()}
            conditions = [item for item in self.conditions if item.field != field or item.value in selected]
            existing = {item.value for item in conditions if item.field == field}
            conditions.extend(Condition(field, value) for value in sorted(selected - existing, key=str.casefold))
            self.update_conditions(conditions)
            dialog.destroy()

        ttk.Button(buttons, text="Clear", command=clear).pack(side="left")
        ttk.Button(buttons, text="Apply", command=apply).pack(side="right")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=8)
        refresh()

    def copy_dialog(self):
        if self.totals is None or self.busy:
            return
        dialog = self.dialog("Copy Eru List", "640x340")
        dialog.minsize(420, 260)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Players").pack(anchor="w", pady=(0, 8))
        text = tk.Text(body, wrap="word", height=8, background=self.host.colors["field"], foreground=self.host.colors["text"], insertbackground=self.host.colors["text"], selectbackground=self.host.colors["accent"], selectforeground=self.host.colors["selected_text"])
        text.pack(fill="both", expand=True)
        text.focus_set()

        def copy():
            try:
                output = eru_list(text.get("1.0", "end"), self.totals, self.service.identities)
            except ValueError as exc:
                messagebox.showerror("Copy Eru List", str(exc), parent=dialog)
                return
            self.host.clipboard_clear()
            self.host.clipboard_append(output)
            self.host.update_idletasks()
            self.status.set("Eru player list copied.")
            dialog.destroy()

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Copy", command=copy).pack(side="right")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=8)
