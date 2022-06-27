import tkinter as tk
from functools import partial
from tkinter import *

window = tk.Tk()
window.geometry('400x200')
window.title('Feed the Aliens Login')

# Username
username_label = tk.Label(text="Username")
username_label.pack()
username = StringVar()
username_entry = tk.Entry(textvariable=username)
username_entry.pack()
username_entry.focus_set()

# Password
password_label = tk.Label(text="Password")
password_label.pack()
password_entry = tk.Entry()
password_entry.pack()


def validate(username):
    print(username.get())


# Submit
submit_button = tk.Button(text="Submit", command=partial(validate, username))
submit_button.pack()

window.mainloop()
