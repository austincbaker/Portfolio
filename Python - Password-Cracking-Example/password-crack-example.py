import hashlib

def read_file(name):
    with open(name) as f:
        lines = f.readlines()
    return lines

def main():
    username = []
    password = []
    
    filepath_roc_u = os.path.join(os.getcwd(),"rockyou_500Thousand.txt")
    filepath_shadow = os.path.join(os.getcwd(),"MyShadow.txt")
    rock_u = read_file(filepath_roc_u)
    shadow = read_file(filepath_shadow)
    
    entry = []
    salt = 'RT'
    
    for i in range(len(shadow)):
        entry.append(shadow[i])
        temp = entry[i].replace(':', '-')
        temp2 = temp.replace(':::::::', "")
        temp3 = temp2.replace('$1$RT$', '')
        split = temp3.split('-')
        username.append(split[0])
        password.append(split[1])

    rock_u_hex = []
    for k in range(len(rock_u)):
        hashObject = hashlib.md5((salt+rock_u[k].strip()).encode('utf-8'))
        hashHex = hashObject.hexdigest()
        rock_u_hex.append(hashHex)

    print("Name     Salt            Hash                            Password\n"
          "------------------------------------------------------------------------------------------")
    matchTot = 0
    missTot= 0
    for l in range(len(password)):
        p = password[l]
        match = False
        for m in (range(len(rock_u_hex))):
            rock = rock_u_hex[m]
            if rock == p:
                print(username[l], '\t', salt, '\t', rock, '\t\t', rock_u[m].strip())
                match = True
                matchTot = matchTot+1

        if not match:
            print(username[l], '\t', salt, '\t', password[l])
            missTot += missTot+1

    print("\nNumber hashes: ", matchTot + missTot-1)
    print("Cracked Passwords: ", matchTot)
    print("Unknown Passwords: ", missTot-1)

if __name__ == '__main__':
    main()
