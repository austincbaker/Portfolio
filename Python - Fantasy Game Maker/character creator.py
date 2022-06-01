import random


###Creates the class Character###
class Character:
    def __init__(self, nameIn, genderIn, raceIn, classTypeIn, levelIn):
        self.__name = nameIn
        self.__gender = genderIn
        self.__race = raceIn
        self.__classType = classTypeIn
        self.__level = str(levelIn)
    def getName(self):
        return self.__name
    def getGender(self):
        return self.__gender
    def getRace(self):
        return self.__race
    def getClassType(self):
        return self.__classType
    def getLevel(self):
        return self.__level
    def changeName(self, newName):
        self.__name = newName
    def changeLevel(self, newLevel):
        self.__level = str(newLevel)
    def changeGender(self, newGender):
        self.__gender = newGender
    def changeRace(self, newRace):
        self.__race = newRace
    def changeClassType(self, newClass):
        self.__classType = newClass


### Prompts the user to preform a task ###
def startMenu():
    testForFile()
    print("1) View all my characters")
    print("2) Create a new character")
    print("3) Search for a character") #Eventually by race, gender, class type
    print("4) Change a character")
    print("5) Create a random character")
    print("6) Exit")
    action = eval(input("Welcome to the character builder! What would you like to do? "))
    if action == 1:
        table()
        startMenu()
    elif action == 2:
        characterBuilder(0)
        startMenu()
    elif action == 3:
        name = input("Who are you looking for? ")
        characterSearch(name)
        startMenu()
    elif action == 4:      
        name = input("Which character do you want to edit? ")
        change = input("Do you want to change the name, gender, race, class type or level? ")
        changeCharacter(name, change)
        startMenu()
    elif action == 5:
        numToCreate = eval(input("How many random characters do you want to create? "))
        randomCharacter(0, numToCreate)
        startMenu()
    elif action == 6:
        print("Bye!")
    else:
        print("Not a valid entry, please try again")
        startMenu()

        
### Tests to see if desired file exists, creates it if not ###
def testForFile():
    try:
        infile = open("Python/Mission Maker/Character_List.txt", 'r')
    except FileNotFoundError:
        fileCreator = open("Python/Mission Maker/Character_List.txt", 'w+')
        print("This file didn't exist, but now it does and we created a character to get you started!")
        randomCharacter(1,1)
        startMenu()
    infile.close


### Opens an existing file to read created characters from and creates a list of them ###
def openForReading():
    testForFile()
    nameSentinel = ""
    infile = open("Python/Mission Maker/Character_List.txt", 'r')
    existingName = infile.readline().strip()
    if existingName == "":
        infile.close()
        print("It looks like you didn't have any charactes in there, so I made you one!")
        randomCharacter(0,1)
        infile = open("Python/Mission Maker/Character_List.txt", 'r')
        existingName = infile.readline().strip()    
    existingGender = infile.readline().strip()
    existingRace = infile.readline().strip()
    existingClassType = infile.readline().strip()
    existingLevel = eval(infile.readline().strip())
    existingCharacterList = []
    while existingName != nameSentinel :
        existingCharacter = Character(existingName, existingGender, existingRace, existingClassType, existingLevel)
        existingCharacterList.append(existingCharacter)
        existingName = infile.readline().strip()
        existingGender = infile.readline().strip()
        existingRace = infile.readline().strip()
        existingClassType = infile.readline().strip()
        existingLevel = infile.readline().strip()
    infile.close
    return existingCharacterList


### Replaces a specific line of text in the file ###
def replaceLine(lineNumber, text):
    fileName = "Python/Mission Maker/Character_List.txt"
    linesRead = open(fileName, 'r+').readlines()
    linesRead[lineNumber] = (text + "\n")
    out = open(fileName, 'w+')
    out.writelines(linesRead)
    out.close()


### Reads file to find total number of lines in the file ###
def findTotalNumberOfLines():
    nameSentinel = ""
    counter = 0
    infile = open("Python/Mission Maker/Character_List.txt", 'r')
    reader = infile.readline()
    while reader != nameSentinel :
        reader = infile.readline()
        counter += 1
    infile.close
    totalNumberOfLines = counter
    infile.close()
    return totalNumberOfLines


### Finds lines to a specific character in the file ###
def findLinesToCharacter(name):
    nameSentinel = str(name)
    counter = 0
    infile = open("Python/Mission Maker/Character_List.txt", 'r')
    listEnd = findTotalNumberOfLines()
    finder = infile.readline().strip()
    while finder != nameSentinel:
        if finder == nameSentinel:
            infile.close()
        elif (finder == nameSentinel and counter == 0):
            counter = 0
            infile.close()
        elif counter == listEnd:
            counter = False
            break
        else:
            finder = infile.readline().strip()
            counter += 1
    infile.close()
    return counter


### Writes and appends to a text file named Character List, creates file if necessary ###
### Variables based in characterBuilder() ###
def fileWriting(newFile,listName,i):
    openFile = open("Python/Mission Maker/Character_List.txt", 'a+')
    if newFile == 1:
        openFile.write(listName[i].getName())
        openFile.write("\n")
        openFile.write(listName[i].getGender())
        openFile.write("\n")
        openFile.write(listName[i].getRace())
        openFile.write("\n")
        openFile.write(listName[i].getClassType())
        openFile.write("\n")
        openFile.write(listName[i].getLevel())
    else:
        openFile.write(listName[i].getName())
        openFile.write("\n")
        openFile.write(listName[i].getGender())
        openFile.write("\n")
        openFile.write(listName[i].getRace())
        openFile.write("\n")
        openFile.write(listName[i].getClassType())
        openFile.write("\n")
        openFile.write(listName[i].getLevel())
        openFile.write("\n")
    openFile.close


### Prints a table based on previously created characters from text file ###
def table():
    existingCharacterList = openForReading()
    print("-" *100)
    print(('{:<25}'.format('Name')),('{:<10}'.format('Gender')), ('{:<20}'.format('Race')), ('{:<20}'.format('Class Type')), ('{:<5}'.format('level')))
    print("-" *100)
    for i in range(len(existingCharacterList)):
        print(format(existingCharacterList[i].getName(), "25s"),format(existingCharacterList[i].getGender(), "10s"), format(existingCharacterList[i].getRace(), "20s"), format(existingCharacterList[i].getClassType(), "20s"), existingCharacterList[i].getLevel(), "\t")
    print("-" * 100)


def characterBuilder(newFile):
    characterList =[]
    i = 0
    nextChar = "yes"
    while nextChar == "yes":
        name = input("Enter the character name: ")
        gender = input("Enter the gender: ")
        race = input("Enter the race: ")
        classType = input("Enter the class type: ")
        level = eval(input("Enter the level of the character: "))
        level = str(level)
        createdCharacter = Character(name, gender, race, classType, level)
        characterList.append(createdCharacter)
        fileWriting(newFile, characterList, i)
        print("Please welcome",characterList[i].getName(), "a level", characterList[i].getLevel(), characterList[i].getRace(), characterList[i].getGender() , characterList[i].getClassType())
        i += 1
        nextChar = input("Do you want to create another character? ")
    return characterList


def characterSearch(name):
    existingCharacterList = openForReading()
    i = 0
    while i in range(len(existingCharacterList)):
        if existingCharacterList[i].getName() == name:
            print("-" *100)
            print(('{:<25}'.format('Name')),('{:<10}'.format('Gender')), ('{:<20}'.format('Race')), ('{:<20}'.format('Class Type')), ('{:<5}'.format('Level')))
            print("-" *100)
            print(format(existingCharacterList[i].getName(), "25s"),format(existingCharacterList[i].getGender(), "10s"), format(existingCharacterList[i].getRace(), "20s"), format(existingCharacterList[i].getClassType(), "20s"), existingCharacterList[i].getLevel(), "\t")
            print("-" *100)
            break
        else:
            i += 1


def changeCharacter(name, change):
    existingCharacterList = openForReading()
    if change == "name":
        i = 0
        j = 0
        #j is the number of lines below the character name in the txt file
        findLinesToCharacter(name)
        k = findLinesToCharacter(name)
        l = j + k
        while i in range(len(existingCharacterList)):
            if k == False:
                print("Couldn't find that character, check your spelling and case.")
                break
            if existingCharacterList[i].getName() == name:
                newName = input("What would you like their new name to be? ")
                existingCharacterList[i].changeName(newName)
                print("The character is now", format(existingCharacterList[i].getName(), "25s"),format(existingCharacterList[i].getGender(), "10s"), format(existingCharacterList[i].getRace(), "20s"), format(existingCharacterList[i].getClassType(), "20s"), existingCharacterList[i].getLevel(), "\t")
                break
            else:
                i += 1
        replaceLine(l, existingCharacterList[i].getName())
    elif change == "gender":
        i = 0
        j = 1
        findLinesToCharacter(name)
        k = findLinesToCharacter(name)
        l = j + k
        while i in range(len(existingCharacterList)):
            if k == False:
                print("Couldn't find that character, check your spelling and case.")
                break
            if existingCharacterList[i].getName() == name:
                newGender = input("What would you like their new gender to be? ")
                existingCharacterList[i].changeGender(newGender)
                print("The character is now", format(existingCharacterList[i].getName(), "25s"),format(existingCharacterList[i].getGender(), "10s"), format(existingCharacterList[i].getRace(), "20s"), format(existingCharacterList[i].getClassType(), "20s"), existingCharacterList[i].getLevel(), "\t")
                break
            else:
                i += 1
        replaceLine(l, existingCharacterList[i].getGender())
    elif change == "race":
        i = 0
        j = 2
        findLinesToCharacter(name)
        k = findLinesToCharacter(name)
        l = j + k
        while i in range(len(existingCharacterList)):
            if k == False:
                print("Couldn't find that character, check your spelling and case.")
                break
            if existingCharacterList[i].getName() == name:
                newRace = input("What would you like their new race to be? ")
                existingCharacterList[i].changeRace(newRace)
                print("The character is now", format(existingCharacterList[i].getName(), "25s"),format(existingCharacterList[i].getGender(), "10s"), format(existingCharacterList[i].getRace(), "20s"), format(existingCharacterList[i].getClassType(), "20s"), existingCharacterList[i].getLevel(), "\t")
                break             
            else:
                i += 1
        replaceLine(l, existingCharacterList[i].getRace())
    elif change == "class":
        i = 0
        j = 3
        findLinesToCharacter(name)
        k = findLinesToCharacter(name)
        l = j + k
        while i in range(len(existingCharacterList)):
            if k == False:
                print("Couldn't find that character, check your spelling and case.")
                break
            if existingCharacterList[i].getName() == name:
                newClass = input("What would you like their new class to be? ")
                existingCharacterList[i].changeClass(newClass)
                print("The character is now", format(existingCharacterList[i].getName(), "25s"),format(existingCharacterList[i].getGender(), "10s"), format(existingCharacterList[i].getRace(), "20s"), format(existingCharacterList[i].getClassType(), "20s"), existingCharacterList[i].getLevel(), "\t")
                break
            else:
                i += 1
        replaceLine(l, existingCharacterList[i].getClass())
    elif change == "level":
        i = 0
        j = 4
        findLinesToCharacter(name)
        k = findLinesToCharacter(name)
        l = j + k
        while i in range(len(existingCharacterList)):
            if k == False:
                print("Couldn't find that character, check your spelling and case.")
                break
            if existingCharacterList[i].getName() == name:
                newLevel = input("What would you like their new level to be? ")
                existingCharacterList[i].changeLevel(newLevel)
                print("The character is now", format(existingCharacterList[i].getName(), "25s"),format(existingCharacterList[i].getGender(), "10s"), format(existingCharacterList[i].getRace(), "20s"), format(existingCharacterList[i].getClassType(), "20s"), existingCharacterList[i].getLevel(), "\t")
                print(i,j,k,l)
                break              
            else:
                i += 1
        replaceLine(l, existingCharacterList[i].getLevel())
    else:
        print("That is not a valid choice. Returning to the menu.")


def randomCharacter(newFile, numToCreate):

    listOfRaces = ["Dragonborn","Dwarf","Elf","Half Elf",'Half Orc','Halfling','Human','Tiefling','Aarakocra','Aasimar','Bug Bear','Firbolg','Goblin','Grung','Hobgoblin','Kenku','Kobold','Lizardfolk','Orc','Tabaxi','Triton','Yuan-Ti', 'Pureblood','Changeling','Eladrin','Genasi','Goliath','Minotaur','Shifter','Warforged', 'Gith']
    listOfClasses = ['Barbarian','Bard','Cleric','Druid','Fighter','Monk','Paladin','Ranger','Rogue','Sorcerer','Warlock','Wizard']
    nameListFile = open("Python/Mission Maker/Characte_ Name_List.txt", 'r')
    readNameToList = nameListFile.readline().strip()
    listOfNames = []
    while readNameToList != "-1":
        listOfNames.append(readNameToList)
        readNameToList = nameListFile.readline().strip()
    randomCharacterList = []
    i = 0
    while numToCreate >= 1:
        randomName = random.randint(0,len(listOfNames))
        j = randomName
        randomRace = random.randint(0, len(listOfRaces))
        k = randomRace
        randomGender = random.randint(1,2)
        if randomGender == 1:
            randomGender = "Female"
        else:
            randomGender = "Male"
        randomClass = random.randint(0, len(listOfClasses))
        m = randomClass
        randomLevel = random.randint(1,20)
        randomCharacter = Character(listOfNames[j], randomGender, listOfRaces[k], listOfClasses[m], randomLevel)
        randomCharacterList.append(randomCharacter)
        print("Say hello to ", randomCharacterList[i].getName(),"a level" , randomCharacterList[i].getLevel(), randomCharacterList[i].getGender(), randomCharacterList[i].getRace(), randomCharacterList[i].getClassType())
        fileWriting(newFile, randomCharacterList, i)
        i += 1
        numToCreate -= 1



startMenu()
