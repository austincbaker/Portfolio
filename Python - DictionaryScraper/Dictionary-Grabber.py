import requests as requests
from bs4 import BeautifulSoup
from os.path import join
import re
import tkinter as tk
from tkinter import filedialog

def dialog():
    root = tk.Tk()
    root.withdraw()
    words_to_define = filedialog.askopenfilename()
    file_to_write = filedialog.asksaveasfilename()
    print(words_to_define)
    print(file_to_write)



class VocabWord:
    def __init__(self):
        self.word = None
        self.preposition = None
        self.definition = None


def write(word, path):
    root = tk.Tk()
    root.withdraw()
    try:
        file = open(join(path), 'a', encoding="utf-8")  # Trying to create a new file or open one
        string = f"{word.word}\n{word.preposition}\n{word.definition}\n\n "
        file.write(string)
        file.close()
        return True

    except:
        print('Something went wrong writing the definition to file')
        quit(-1)
        return False


def search(WordList):
    path = filedialog.asksaveasfilename()
    word_object_list = WordList
    defined_words_list = []
    x=0
    print("defining...")
    for vocab_word in word_object_list:
        x+=1
        duplicate = False
        if x % 50 == 0:
            print(f"{x} words of {len(word_object_list)} defined")
        URL = 'https://www.dictionary.com/browse/' + vocab_word.word
        #URL = 'https://www.dictionary.com/browse/' + vocab_word.word
        s = requests.Session()
        s.max_redirects = 100
        s.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.131 Safari/537.36'
        requests.adapters.DEFAULT_RETRIES = 10  # Increase the number of reconnections
        s = requests.session()
        s.keep_alive = False  # Close redundant connections
        r = s.get(URL)
        soup = BeautifulSoup(r.content, 'html.parser')
        results = soup.find(id='base-pw')
        s.close()
        r.close()

        word_elements = results.find_all()
        r.close()
        for word_elem in word_elements:
            vocab_word.definition = word_elem.find('span', class_='one-click-content')
            vocab_word.preposition = word_elem.find('span', class_='luna-pos')
            if (vocab_word.definition != None and vocab_word.preposition != None):
                if len(defined_words_list) < 1:
                    vocab_word.definition = vocab_word.definition.text
                    vocab_word.preposition = vocab_word.preposition.text
                    defined_words_list.append(vocab_word)
                    write(vocab_word, path)
                else:
                    for defined_word in defined_words_list:
                        if defined_word.word == vocab_word.word and vocab_word.definition != None:
                            if defined_word.definition.text == vocab_word.definition.text:
                                duplicate = True
                                break
                            else:
                                vocab_word.definition = vocab_word.definition.text
                                vocab_word.preposition = vocab_word.preposition.text
                                defined_words_list.append(vocab_word)
                                write(vocab_word, path)
                                break
                    if duplicate == False:
                        vocab_word.definition = vocab_word.definition.text
                        vocab_word.preposition = vocab_word.preposition.text
                        write(vocab_word, path)
                        defined_words_list.append(vocab_word)
                    #break
                #break
            break



def openWords():
    root = tk.Tk()
    root.withdraw()
    words_to_define = open(filedialog.askopenfilename())
    word_objects_list = []
    sorted_word_list = []
    with words_to_define as f:
        lines_read = f.readlines()
        print("reading...")
        for line in lines_read:
            # print(line.split())
            for word in line.split():
                word = re.sub(r'[^\w\s]', '', word).lower()
                if word not in sorted_word_list and len(word) > 3:
                    sorted_word_list.append(word)
        words_to_define.close()
        f.close()
    sorted_word_list = sorted(sorted_word_list)
    for word in sorted_word_list:
        vocab_word = VocabWord()
        vocab_word.word = word
        word_objects_list.append(vocab_word)

    #for word in word_objects_list:
     #   print(word.word)
    return word_objects_list

if __name__ == '__main__':
    word_object_list = openWords()
    search(word_object_list)

