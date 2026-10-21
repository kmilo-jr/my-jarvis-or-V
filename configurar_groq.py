"""Local encrypted credential entry for Groq."""
import tkinter as tk
from tkinter import messagebox
import webbrowser
from brain.groq_client import save_key


def main():
    root = tk.Tk()
    root.title('V — Configurar Groq')
    root.geometry('630x290')
    tk.Label(root, text='Groq — IA do V', font=('Segoe UI', 15, 'bold')).pack(pady=16)
    tk.Label(root, text='Use uma chave de uma conta no plano Free. Existem limites de uso.').pack()
    entry = tk.Entry(root, show='•', width=66)
    entry.pack(padx=20, pady=15)
    tk.Button(root, text='Criar chave no Groq', command=lambda: webbrowser.open('https://console.groq.com/keys')).pack()

    def save():
        try:
            save_key(entry.get())
        except Exception:
            messagebox.showerror('V', 'Não foi possível proteger e salvar a chave. Confira a entrada e a instalação do pywin32.')
            return
        entry.delete(0, 'end')
        messagebox.showinfo('V', 'Chave salva com proteção do Windows.\nExecute testar_groq.bat para confirmar a conexão.\nDepois reabra o V.')
        root.destroy()

    tk.Button(root, text='Salvar chave protegida', command=save).pack(pady=12)
    tk.Label(root, text='A prioridade segue a configuração do V. A chave é protegida pelo Windows.').pack()
    entry.focus_set()
    root.mainloop()


if __name__ == '__main__':
    main()
