import tkinter as tk
from tkinter import ttk, messagebox
import time, re
from datetime import datetime
import database_manager

class StructDBGUI:
    def __init__(self, r):
        self.r, self.db = r, database_manager.DatabaseManager()
        self.r.title("StructDB - Professional Engine"); self.r.geometry("1400x800")
        self.c_tbl = None; self._th(); self.r.withdraw(); self._sp()

    def _sp(self):
        s = tk.Toplevel(self.r); s.overrideredirect(1); s.geometry("500x300+450+250"); s.configure(bg=self.c["bg1"])
        tk.Label(s, text="StructDB", font=('Consolas', 48, 'bold'), fg=self.c["fg1"], bg=self.c["bg1"]).pack(expand=1, pady=(50, 0))
        tk.Label(s, text="Professional Database Engine", font=('Segoe UI', 14), fg=self.c["fg3"], bg=self.c["bg1"]).pack()
        self.p = ttk.Progressbar(s, orient="horizontal", length=300, mode="indeterminate"); self.p.pack(pady=20); self.p.start(15)
        tk.Label(s, text="Initializing components...", font=('Segoe UI', 10), fg=self.c["fg2"], bg=self.c["bg1"]).pack(side="bottom", pady=20)
        self.r.after(2000, lambda: [self.p.stop(), s.destroy(), self.r.deiconify(), self._sh_log()])

    def _th(self):
        self.c = {"bg1":"#040D21","bg2":"#0A1931","bg3":"#122A54","bg4":"#18366B","fg1":"#FFFFFF","fg2":"#E8F0FE","fg3":"#8AB4F8","fg4":"#4285F4","grn":"#34A853","red":"#EA4335","blu":"#4285F4","sql_kw":"#C678DD","sql_str":"#98C379","sql_num":"#D19A66","sql_fn":"#61AFEF"}
        s = ttk.Style(); s.theme_use('clam'); self.r.configure(bg=self.c["bg1"])
        for e, bg, fg in [('TFrame', "bg2", None), ('TLabel', "bg2", "fg3"), ('TLabelframe', "bg2", "fg1"), ('TLabelframe.Label', "bg2", "fg1"), ('TButton', "bg3", "fg1"), ('Primary.TButton', "blu", "fg1"), ('TNotebook', "bg2", None), ('TNotebook.Tab', "bg1", "fg3"), ('Treeview.Heading', "bg3", "fg1")]: kw={'background':self.c[bg]}; (kw.update({'foreground':self.c[fg]}) if fg else None); s.configure(e, **kw)
        s.configure('TEntry', fieldbackground=self.c["bg4"], foreground=self.c["fg1"], insertcolor=self.c["fg1"])
        s.configure('TCombobox', fieldbackground=self.c["bg4"], foreground=self.c["fg1"], insertcolor=self.c["fg1"])
        s.configure('Treeview', fieldbackground=self.c["bg4"], background=self.c["bg4"], foreground=self.c["fg2"])
        s.map('Treeview', fieldbackground=[('', self.c["bg4"])], background=[('selected', self.c["blu"])], foreground=[('selected', self.c["fg1"])])
        s.map('TEntry', fieldbackground=[('', self.c["bg4"])])
        s.map('TCombobox', fieldbackground=[('', self.c["bg4"])])
        s.map('TButton', background=[('active', self.c["fg4"]), ('pressed', self.c["blu"])]); s.map('TNotebook.Tab', background=[('selected', self.c["bg3"])], foreground=[('selected', self.c["fg1"])])

    def _cl(self): [w.destroy() for w in self.r.winfo_children()]

    def _auth(self, t, r=0):
        self._cl(); c = tk.Frame(self.r, bg=self.c["bg1"]); c.place(relx=0.5, rely=0.5, anchor='center')
        tk.Label(c, text=t, font=('Consolas', 32, 'bold'), fg=self.c["fg1"], bg=self.c["bg1"]).pack(pady=(0,20))
        f = ttk.LabelFrame(c, text=" [ SECURE ACCESS ] ", padding=(30, 20)); f.pack(fill='both', expand=1); e = {}
        for i, fld in enumerate(["username", "password"] + (["confirm"] if r else [])):
            ttk.Label(f, text=fld.upper()).grid(row=i*2, column=0, sticky='w', pady=(10 if i==0 else 5, 5))
            e[fld] = ttk.Entry(f, width=35, show='●' if fld != "username" else ''); e[fld].grid(row=i*2+1, column=0, pady=(0, 15))
        bf = tk.Frame(f, bg=self.c["bg2"]); bf.grid(row=6, column=0, pady=20)
        return e, bf

    def _sh_log(self):
        self.e, bf = self._auth("StructDB Login"); ttk.Button(bf, text="LOGIN", command=self._log, style='Primary.TButton').pack(side='left', padx=5); ttk.Button(bf, text="Register", command=self._sh_reg).pack(side='left', padx=5); self.r.bind('<Return>', lambda e: self._log())

    def _sh_reg(self):
        self.e, bf = self._auth("Register New User", 1); ttk.Button(bf, text="REGISTER", command=self._reg, style='Primary.TButton').pack(side='left', padx=5); ttk.Button(bf, text="Back", command=self._sh_log).pack(side='left', padx=5); self.r.unbind('<Return>')

    def _reg(self):
        u, p, c = [self.e[k].get().strip() for k in ("username", "password", "confirm")]
        if not u or not p: return messagebox.showerror("Err", "Fields required")
        if p != c: return messagebox.showerror("Err", "Passwords mismatch")
        try: self.db.register_user(u, p); messagebox.showinfo("OK", "Registered!"); self._sh_log()
        except Exception as e: messagebox.showerror("Err", str(e))

    def _log(self):
        u, p = [self.e[k].get().strip() for k in ("username", "password")]
        if not u or not p: return messagebox.showerror("Err", "Fields required")
        try: self.db.login(u, p); self._main()
        except Exception as e: messagebox.showerror("Err", str(e))

    def _m_t(self, p, h, s='normal'):
        f = tk.Frame(p, bg=self.c["bg4"], bd=2, relief='solid'); f.pack(fill='both', expand=1, padx=10, pady=10)
        t = tk.Text(f, height=h, bg=self.c["bg4"], fg=self.c["fg1"], insertbackground=self.c["fg1"], font=('Consolas', 11), bd=0, state=s); t.pack(side='left', fill='both', expand=1)
        sb = ttk.Scrollbar(f, command=t.yview); sb.pack(side='right', fill='y'); t.config(yscrollcommand=sb.set); return t

    def _main(self):
        self._cl(); self.r.unbind('<Return>')
        tb = tk.Frame(self.r, bg=self.c["bg3"], height=50); tb.pack(side='top', fill='x')
        tk.Label(tb, text=f"● USER: {self.db.current_user.upper()}", font=('Consolas', 12, 'bold'), fg=self.c["grn"], bg=self.c["bg3"]).pack(side='left', padx=20)
        ttk.Button(tb, text="LOGOUT", command=lambda: (self.db.logout(), self._sh_log()) if messagebox.askyesno("Confirm", "Logout?") else 0).pack(side='right', padx=10, pady=10)
        self.nb = ttk.Notebook(self.r); self.nb.pack(fill='both', expand=1); self.fs = {n: ttk.Frame(self.nb) for n in ['q','g','d','e']}
        for f, t in [(self.fs['q'], '⚡ QUERY'), (self.fs['g'], '🖥 GUI'), (self.fs['d'], '📈 DASHBOARD'), (self.fs['e'], '🕸 ER DIAGRAM')]: self.nb.add(f, text=t)
        self._s_q(); self._s_g(); self._s_d(); self._s_e()
        self.nb.bind('<<NotebookTabChanged>>', lambda e: [self._r_g, self._r_d, self._r_e][self.nb.index('current')-1]() if self.nb.index('current')>0 else 0)

    def _hl(self, e=None):
        c = self.q_txt.get('1.0', 'end')
        tgs = {'kw':(r'\b(SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|DROP|TABLE|INDEX|ON|USE|SHOW|DATABASES|DESCRIBE|JOIN|INNER|AND|OR|ORDER BY|LIMIT|BEGIN|COMMIT|ROLLBACK|EXPLAIN|IMPORT|ASC|DESC)\b', self.c["sql_kw"]), 'fn':(r'\b(COUNT|SUM|AVG|MIN|MAX)\b', self.c["sql_fn"]), 'str':(r'\'[^\']*\'|\"[^\"]*\"', self.c["sql_str"]), 'num':(r'\b\d+(\.\d+)?\b', self.c["sql_num"])}
        for t, (p, clr) in tgs.items():
            self.q_txt.tag_configure(t, foreground=clr, font=('Consolas', 11, 'bold') if t=='kw' else None); self.q_txt.tag_remove(t, '1.0', 'end')
            for m in re.finditer(p, c, re.I): self.q_txt.tag_add(t, f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def _s_q(self):
        qf = tk.Frame(self.fs['q'], bg=self.c["bg2"]); qf.pack(fill='both', expand=1, padx=10, pady=10)
        i = ttk.LabelFrame(qf, text=" [ SQL ] "); i.pack(fill='x', pady=(0, 10)); self.q_txt = self._m_t(i, 6)
        self.q_txt.bind('<Return>', lambda e: [self._rq(self.q_txt.get("insert linestart", "insert lineend").strip(), 1), 'break'][1] if self.q_txt.get("insert linestart", "insert lineend").strip() else None); self.q_txt.bind('<KeyRelease>', self._hl)
        bf = tk.Frame(i, bg=self.c["bg2"]); bf.pack(fill='x', padx=10, pady=(0, 10))
        for t, c in [("▶ EXEC", lambda: [self._rq(q) for q in self.q_txt.get('1.0', 'end').split(';') if q.strip()] if self.q_txt.get('1.0', 'end').strip() else self._msg("⚠ No query", err=1)), ("Clr", lambda: self.q_txt.delete('1.0', 'end')), ("Hist", self._hist)]: ttk.Button(bf, text=t, command=c).pack(side='left', padx=5)
        rf = ttk.LabelFrame(qf, text=" [ RES ] "); rf.pack(fill='both', expand=1)
        tf = tk.Frame(rf, bg=self.c["bg2"]); tf.pack(fill='both', expand=1, padx=10, pady=10); self.rtv = ttk.Treeview(tf, selectmode='browse')
        sy, sx = ttk.Scrollbar(tf, orient='vertical', command=self.rtv.yview), ttk.Scrollbar(tf, orient='horizontal', command=self.rtv.xview); self.rtv.config(yscrollcommand=sy.set, xscrollcommand=sx.set); sy.pack(side='right', fill='y'); sx.pack(side='bottom', fill='x'); self.rtv.pack(fill='both', expand=1)
        self.r_msg = tk.Text(rf, height=6, bg=self.c["bg4"], fg=self.c["fg1"], font=('Consolas', 11), bd=0, state='disabled'); self.r_msg.pack(fill='x', padx=10, pady=(0, 10))

    def _rq(self, q, il=0):
        s = time.time()
        try:
            r = self.db.execute_query(q); t = (time.time() - s) * 1000
            if type(r)==list: self._stbl(r, q, t)
            else: self._msg(f"✓ {r}\nTime: {t:.2f} ms", ok=1, q=q)
            if il: self.q_txt.insert("insert", "\n"); self._hl()
            self.q_txt.see("insert" if il else 'end')
        except Exception as e: self._msg(f"✗ ERR: {e}\nTime: {(time.time() - s)*1000:.2f} ms", err=1, q=q)

    def _msg(self, t, ok=0, err=0, q=None, c=1):
        m = self.r_msg; m.config(state='normal'); m.delete('1.0', 'end')
        if q: m.insert('end', f"➤ Exec: {q}\n")
        m.insert('end', t); tag = 'ok' if ok else 'err' if err else ''
        if tag: m.tag_add(tag, '1.0', 'end'); m.tag_config(tag, foreground=self.c["grn"] if ok else self.c["red"])
        m.config(state='disabled')
        if c: self.rtv.delete(*self.rtv.get_children()); self.rtv['columns'] = []

    def _stbl(self, recs, q, t):
        self.rtv.delete(*self.rtv.get_children())
        if not recs: return self._msg(f"✓ 0 rows\nTime: {t:.2f} ms", ok=1, q=q)
        c = list(recs[0].keys()); self.rtv['columns'] = c; self.rtv['show'] = 'headings'
        for col in c: self.rtv.heading(col, text=col); self.rtv.column(col, width=150)
        for i, r in enumerate(recs): self.rtv.insert('', 'end', values=[str(r.get(k,'')) for k in c], tags=('even' if i%2==0 else 'odd',))
        self.rtv.tag_configure('even', background=self.c["bg4"]); self.rtv.tag_configure('odd', background=self.c["bg2"])
        self._msg(f"✓ {len(recs)} row(s)\nTime: {t:.2f} ms", ok=1, q=q, c=0)

    def _s_g(self):
        sf = ttk.LabelFrame(self.fs['g'], text=" [ SEL ] "); sf.pack(fill='x', padx=10, pady=10)
        tk.Label(sf, text="DB:", bg=self.c["bg2"], fg=self.c["fg2"]).pack(side='left', padx=5); self.ldb = tk.Label(sf, text="None", bg=self.c["bg2"], fg=self.c["fg3"]); self.ldb.pack(side='left', padx=5)
        tk.Label(sf, text="Tbl:", bg=self.c["bg2"], fg=self.c["fg2"]).pack(side='left', padx=5); self.cmb = ttk.Combobox(sf, state='readonly', width=20); self.cmb.pack(side='left', padx=5); self.cmb.bind('<<ComboboxSelected>>', lambda e: self._ltbl())
        cf = tk.Frame(self.fs['g'], bg=self.c["bg2"]); cf.pack(fill='both', expand=1, padx=10, pady=(0,10))
        ff = ttk.LabelFrame(cf, text=" [ FRM ] "); ff.pack(side='left', fill='both', expand=1, padx=(0,5)); self.fc = tk.Frame(ff, bg=self.c["bg2"]); self.fc.pack(fill='both', expand=1, padx=5, pady=5); self.flds = {}
        bf = tk.Frame(ff, bg=self.c["bg2"]); bf.pack(fill='x', padx=5, pady=5)
        for t, c in [("Ins", lambda: self._dbop('ins')), ("Upd", lambda: self._dbop('upd')), ("Del", lambda: self._dbop('del')), ("Clr", lambda: [e.delete(0, 'end') for e in self.flds.values()]), ("CSV", lambda: messagebox.showinfo("OK", self.db.export_to_csv(self.c_tbl, f"{self.c_tbl}.csv")))]: ttk.Button(bf, text=t, command=c).pack(side='left', padx=2)
        tf = ttk.LabelFrame(cf, text=" [ DAT ] "); tf.pack(side='right', fill='both', expand=1); self.tv = ttk.Treeview(tf, selectmode='browse'); sy, sx = ttk.Scrollbar(tf, orient='vertical', command=self.tv.yview), ttk.Scrollbar(tf, orient='horizontal', command=self.tv.xview); self.tv.config(yscrollcommand=sy.set, xscrollcommand=sx.set); sy.pack(side='right', fill='y'); sx.pack(side='bottom', fill='x'); self.tv.pack(fill='both', expand=1); self.tv.bind('<<TreeviewSelect>>', lambda e: [e.delete(0, 'end') for e in self.flds.values()] or [self.flds[c].insert(0, str(v)) for c, v in zip(self.tv['columns'], self.tv.item(self.tv.selection()[0])['values']) if c in self.flds] if self.tv.selection() else 0)

    def _ltbl(self):
        self.c_tbl = self.cmb.get(); d = self.db.get_current_database()
        if not self.c_tbl or not d: return
        [w.destroy() for w in self.fc.winfo_children()]; self.flds = {}; tbl = d.tables[self.c_tbl]
        for i, c in enumerate(tbl['columns']): tk.Label(self.fc, text=c+":", bg=self.c["bg2"], fg=self.c["fg2"]).grid(row=i, column=0, pady=5); e = ttk.Entry(self.fc, width=30); e.grid(row=i, column=1, pady=5); self.flds[c] = e
        self._lr()

    def _lr(self):
        self.tv.delete(*self.tv.get_children()); d = self.db.get_current_database(); recs = d.select_records(self.c_tbl); c = list(recs[0].keys()) if recs else d.tables[self.c_tbl]['columns']; self.tv['columns'] = c; self.tv['show'] = 'headings'
        for col in c: self.tv.heading(col, text=col); self.tv.column(col, width=100)
        for r in recs: self.tv.insert('', 'end', values=[str(r.get(k,'')) for k in c])

    def _dbop(self, o):
        if not self.c_tbl: return messagebox.showerror("Err", "Select table")
        d = self.db.get_current_database(); t = d.tables[self.c_tbl]; pk = t['primary_key']
        try:
            if o == 'ins': d.insert_record(self.c_tbl, [self.flds[c].get() for c in t['columns']])
            else:
                if not self.tv.selection(): return messagebox.showerror("Err", "Select record")
                if o == 'del' and not messagebox.askyesno("Confirm", "Delete?"): return
                wc = [(pk, '=', self.flds[pk].get())]
                d.update_records(self.c_tbl, {c:e.get() for c,e in self.flds.items() if c!=pk}, wc) if o == 'upd' else d.delete_records(self.c_tbl, wc)
            self.db.save_database(self.db.current_database); self._lr(); [e.delete(0, 'end') for e in self.flds.values()]; messagebox.showinfo("OK", "Success!")
        except Exception as e: messagebox.showerror("Err", str(e))

    def _s_d(self): self.dc = tk.Canvas(self.fs['d'], bg=self.c["bg2"], highlightthickness=0); self.dc.pack(fill='both', expand=1, padx=20, pady=20)
    def _r_d(self):
        self.dc.delete("all"); d = self.db.current_database
        if not d or not self.db.get_current_database().tables: return self.dc.create_text(700, 350, text="No DB/Tables", fill=self.c["fg2"], font=("Segoe UI", 16))
        do = self.db.get_current_database(); ts = do.tables; tn = list(ts.keys()); rc = [len(t['records']) for t in ts.values()]; mc = max(rc) or 1
        self.dc.create_text(700, 50, text=f"Dash: {do.name}", fill=self.c["fg1"], font=("Segoe UI", 24, "bold")); bw = 1000 / (len(tn) * 2)
        self.dc.create_line(150, 150, 150, 550, fill=self.c["fg2"], width=2); self.dc.create_line(150, 550, 1150, 550, fill=self.c["fg2"], width=2)
        for i, (n, c) in enumerate(zip(tn, rc)):
            x0 = 150 + (i * 2 + 1) * bw; y0 = 550 - (c / mc) * 400; self.dc.create_rectangle(x0, y0, x0 + bw, 550, fill=self.c["blu"], outline=self.c["fg4"])
            self.dc.create_text(x0 + bw/2, y0 - 15, text=str(c), fill=self.c["fg1"], font=("Consolas", 12)); self.dc.create_text(x0 + bw/2, 570, text=n, fill=self.c["fg2"], font=("Segoe UI", 12), angle=45)
        self.dc.create_text(300, 650, text=f"Tables: {len(tn)}", fill=self.c["grn"], font=("Segoe UI", 16)); self.dc.create_text(700, 650, text=f"Records: {sum(rc)}", fill=self.c["grn"], font=("Segoe UI", 16)); self.dc.create_text(1100, 650, text=f"Queries: {len(self.db.query_history)}", fill=self.c["grn"], font=("Segoe UI", 16))

    def _s_e(self): self.ec = tk.Canvas(self.fs['e'], bg=self.c["bg2"], highlightthickness=0); self.ec.pack(fill='both', expand=1, padx=20, pady=20)
    def _r_e(self):
        self.ec.delete("all"); d = self.db.current_database
        if not d or not self.db.get_current_database().tables: return self.ec.create_text(700, 350, text="No DB/Tables", fill=self.c["fg2"], font=("Segoe UI", 16))
        do = self.db.get_current_database(); ts = do.tables; self.ec.create_text(700, 30, text="ER Diagram", fill=self.c["fg1"], font=("Segoe UI", 20, "bold"))
        for i, (n, t) in enumerate(ts.items()):
            x = 100 + (i % 3) * 350; y = 100 + (i // 3) * 250; h = 40 + len(t['columns']) * 25
            self.ec.create_rectangle(x, y, x + 250, y + h, fill=self.c["bg4"], outline=self.c["fg4"], width=2); self.ec.create_rectangle(x, y, x + 250, y + 35, fill=self.c["bg3"], outline=self.c["fg4"], width=2)
            self.ec.create_text(x + 125, y + 17, text=n.upper(), fill=self.c["fg1"], font=("Segoe UI", 12, "bold"))
            for j, c in enumerate(t['columns']): self.ec.create_text(x + 15, y + 50 + j * 25, text=f"{'🔑 ' if c == t['primary_key'] else '   '}{c}{' (Idx)' if c in do.bt_indexes.get(n, {}) else ''}", fill=self.c["grn"] if c == t['primary_key'] else self.c["fg2"], font=("Consolas", 11), anchor="w")

    def _r_g(self): d = self.db.current_database; self.ldb.config(text=d or "None", fg=self.c["grn"] if d else self.c["red"]); self.cmb['values'] = list(self.db.get_current_database().tables.keys()) if d else []
    def _hist(self):
        w = tk.Toplevel(self.r); w.title("History"); w.geometry("600x400"); w.configure(bg=self.c["bg2"]); tk.Label(w, text="Click a query to load it", bg=self.c["bg2"], fg=self.c["fg3"], font=("Segoe UI", 12)).pack(pady=10)
        htv = ttk.Treeview(w, columns=('t', 'q'), show='headings', selectmode='browse'); htv.heading('t', text='Time'); htv.heading('q', text='Query'); htv.column('t', width=150); htv.column('q', width=430)
        sy = ttk.Scrollbar(w, orient='vertical', command=htv.yview); htv.config(yscrollcommand=sy.set); sy.pack(side='right', fill='y'); htv.pack(fill='both', expand=1, padx=10, pady=(0, 10))
        for h in reversed(self.db.query_history[-50:]): htv.insert('', 'end', values=[datetime.fromisoformat(h['timestamp']).strftime('%H:%M:%S'), h['query']])
        htv.bind('<Double-1>', lambda e: (self.q_txt.delete('1.0', 'end'), self.q_txt.insert('1.0', htv.item(htv.selection()[0])['values'][1]), self._hl(), w.destroy()) if htv.selection() else 0)