from tkinter import filedialog
import csv
import json
from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile
import os

from requests import patch

#downloads the source data file from openFDA.gov
def download_data():
    url = 'https://download.open.fda.gov/drug/drugsfda/drug-drugsfda-0001-of-0001.json.zip'
    with urlopen(url) as zipped:
        with ZipFile(BytesIO(zipped.read())) as file:
            # Places file in the main directory
            file.extractall(path = '')


def dialog():
    file_to_write = filedialog.asksaveasfilename()
    print(file_to_write)

if __name__ == '__main__':
    
    download_data()
    read_in = "drug-drugsfda-0001-of-0001.json"
    med_list = []
    
    with open(read_in) as rf:
        json_file = json.load(rf)
        all_data = json_file["results"]
        num = range(len(all_data))
        
        for i in range(len(all_data)):
            results_list = all_data[i]
            products_dict = results_list.get('products')
            if products_dict is not None:
                product_information = products_dict[0]
                brand_name = product_information.get('brand_name')
                generic_name = product_information.get('generic_name')
                
                if brand_name is not None:
                    # Just some formatting
                    brand_name = brand_name.replace(" ", "")
                    brand_name = brand_name.replace("  ", " ")
                    if brand_name not in med_list:
                        brand_name = brand_name.lstrip()
                        med_list.append(brand_name.strip())
                        
                if generic_name is not None:
                    generic_name = generic_name.replace(" ", "")
                    generic_name = generic_name.replace("  ", " ")
                    if generic_name not in med_list:
                        generic_name = generic_name.lstrip()
                        med_list.append(generic_name.strip())
                        
            #TODO: In the future, we may want to obtain doses or routes
            #These can all be found in the 'product_information' key
            #as of 6/2022
            
    # Sorting the list and writes it to a csv file
    sorted_med_list = sorted(med_list)
    save_file = filedialog.asksaveasfilename()+".csv"
    with open(save_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=' ', quotechar=' ', quoting=csv.QUOTE_MINIMAL)
        for name in sorted_med_list:
            writer.writerow([name])

    # Removes downloaded json file
    os.remove("drug-drugsfda-0001-of-0001.json")