import divelog_convert
from pathlib import Path

import attr
import numpy
import xmltodict

# import kivy
# kivy.require('2.1.0')
# from kivy.app import App
# from kivy.uix.boxlayout import BoxLayout
# from kivy.uix.gridlayout import GridLayout
# from kivy.uix.label import Label
# from kivy.uix.textinput import TextInput
# from kivy.uix.filechooser import FileChooserListView
# from kivy.uix.button import Button
# from kivy.properties import ObjectProperty
# from kivy.uix.popup import Popup

# class LoadDialog(BoxLayout):
#     selection = ObjectProperty(None)
#     cancel = ObjectProperty(None)

#     def __init__(self, root, **kwargs):
#         super(LoadDialog, self).__init__(**kwargs)

#         self.orientation='vertical'
#         self.size = root.size
#         self.pos = root.pos

#         self._filechooser = FileChooserListView(filters=['*.zxu'])
#         self._filechooser.path = str(Path.home())
#         self.add_widget(self._filechooser)

#         buttons_layout = BoxLayout()
#         buttons_layout.size_hint_y = None
#         buttons_layout.height = 60

#         select_button = Button(text='Select')
#         select_button.bind(on_release=self.selected)
#         buttons_layout.add_widget(select_button)

#         cancel_button = Button(text='Cancel')
#         cancel_button.bind(on_release=self.cancel)
#         buttons_layout.add_widget(cancel_button)
#         # selection(filechooser.path, filechooser.selection)
#         self.add_widget(buttons_layout)
    
#     def selected(self, button_instance):
#         self.selection(self._filechooser.path, self._filechooser.selection)



# class MainWindow(BoxLayout):
#     # https://kivy.org/doc/stable/api-kivy.uix.filechooser.html?highlight=file#kivy.uix.filechooser.FileChooserController

#     def __init__(self, **kwargs):
#         super(MainWindow, self).__init__(**kwargs)

#         self.orientation='vertical'

#         input_layout = GridLayout(cols=2, height=60, size_hint_y = None)
#         input_button = Button(text='Select input file')
#         input_button.bind(on_release=self.show_select)
#         input_layout.add_widget(input_button)
#         self._input_label = Label(text="No file to convert")
#         input_layout.add_widget(self._input_label)
#         self.add_widget(input_layout)

#         output_layout = GridLayout(cols=2, height=60, size_hint_y = None)
#         output_button = Button(text='Select output file')
#         output_button.bind(on_release=self.show_select)
#         output_layout.add_widget(output_button)
#         output_layout.add_widget(Label(text="Output file: "))
#         self.add_widget(output_layout)


#         convert_button = Button(text='Convert')
#         convert_button.bind(on_release=self.convert)
#         self.add_widget(convert_button)

#         self.add_widget(Label(text=f"divelog_convert v{divelog_convert.__version__}", size_hint_y = None, height = 60))

    
#     def convert(self, button_instance):
#         print(f"pipo: {self._filechooser.path}, {self._filechooser.selection}")
#         self._popup.dismiss()

#     def selection(self, path, filenames):
#         # with open(os.path.join(path, filename[0])) as stream:
#         if filenames:
#             print(f"pipo selection {path} / {filenames}")
#             print(f"pipo selection {Path(path) / Path(filenames[0])}")
#             self._input_label.text = str(Path(path) / Path(filenames[0]))
#             self._popup.dismiss()

#     def dismiss_popup(self, button_instance):
#         self._popup.dismiss()

#     def show_select(self, button_instance):
#         content = LoadDialog(selection=self.selection, cancel=self.dismiss_popup, root=self)
#         self._popup = Popup(title="Load file", content=content, size_hint=(0.9, 0.9))
#         self._popup.open()



# class DiveLogConverterApp(App):

#     def build(self):
#         return MainWindow()


from tkinter import *
from tkinter.ttk import *
from tkinter import filedialog
# from tkinter.messagebox import showinfo


class DiveLogConverterApp(Frame):

    def __init__(self, master=None):
        master = master or Tk()
        super().__init__(master)
        self.master.title = f"divelog_convert v{divelog_convert.__version__}"
        self.padding=10
        self.title = f"pipo"
        # self.master.resizable(False, False)
        # frm = ttk.Frame(root, padding=10)

        self.grid()

        Button(self, text='Select a File to convert', command=self.select_input_file).grid(column=0, row=0)
        self._input_label = StringVar()
        self._input_label.set("No file to convert")
        Label(self, textvariable=self._input_label).grid(column=1, row=0)

        Button(self, text='Select a destination', command=self.select_output_file).grid(column=0, row=2)
        self._output_label = StringVar()
        self._output_label.set("No destination file")
        Label(self, textvariable=self._output_label).grid(column=1, row=2)

        Label(self, text=f"").grid(column=0, row=3)
        # Separator(self, orient="horizontal").grid(column=2, row=2)

        Button(self, text="Convert", command=self.convert).grid(column=1, row=4)

        Label(self, text=f"divelog_convert v{divelog_convert.__version__}").grid(column=0, row=5)
        Button(self, text="Quit", command=self.master.destroy).grid(column=1, row=5)

        self.pack()


    def select_input_file(self):
        filetypes = (
            ('zxu files', '*.zxu'),
            # ('All files', '*.*')
        )

        filename = filedialog.askopenfilename(
            title='Load file to convert',
            initialdir=str(Path.home()),
            filetypes=filetypes)
        self._input_label.set(filename)

    def select_output_file(self):
        filetypes = (
            ('zxu files', '*.zxu'),
            # ('All files', '*.*')
        )

        filename = filedialog.asksaveasfilename(
            title='Load file to convert',
            initialdir=str(Path.home()),
            filetypes=filetypes)
        self._output_label.set(filename)

    def convert(self):
        pass

    def run(self):
        self.mainloop()

def main() -> None:
    DiveLogConverterApp().run()

if __name__ == '__main__':
    print("pipo")
    main()
