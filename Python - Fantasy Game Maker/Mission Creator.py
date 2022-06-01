class Mission:
    def __init__(self, missionNameIn, missionTypeIn, questLineIn, startingPointIn, startingNPCIn, keyItemsIn, missionOutlineIn, missionDestinationIn, mainEnemyIn, missionRewardsIn, otherDetailsIn):
        self.__missionName = missionNameIn
        self.__missionType = missionTypeIn
        self.__questLine = questLineIn
        self.__startingPoint = startingPointIn
        self.__startingNPC = startingNPCIn
        self.__keyItems = keyItemsIn
        self.__missionOutline = missionOutlineIn
        self.__missionDestination = missionDestinationIn
        self.__mainEnemy = mainEnemyIn
        self.__missionRewards = missionRewardsIn
        self.__otherDetails = otherDetailsIn
    def getMissionName(self):
        return self.__missionName
    def getMissionType(self):
        return self.__missionType
    def getQuestLine(self):
        return self.__questLine
    def getStartingPoint(self):
        return self.__startingPoint
    def getStartingNPC(self):
        return self.__startingNPC
    def getKeyItems(self):
        return self.__keyItems
    def getMissionOutline(self):
        return self.__missionOutline
    def getMissionDestination(self):
        return self.__missionDestination
    def getMainEnemy(self):
        return self.__mainEnemy
    def getMissionRewards(self):
        return self.__missionRewards
    def getOtherDetails(self):
        return self.__otherDetails

    def changeMissionName(self, newMissionName):
        self.__missionName = newMissionName
    def changeMissionType(self, newMissionType):
        self.__missionType = newMissionType
    def changeStartingPoint(self, newStartingPoint):
        self.__startingPoint = newStartingPoint
    def changeQuestLine(self, newQuestLine):
        self.__questLine = newQuestLine
    def changeStartingNPC(self, newStartingNPC):
        self.__startingNPC = newStartingNPC
    def changeKeyItems(self, newKeyItems):
        self.__keyItems = newKeyItems
    def changeMissionOutline(self, newMissionOutline):
        self.__missionOutline = newMissionOutline
    def changeMissionDestination(self, newMissionDestination):
        self.__missionDestination = newMissionDestination
    def changeMainEnemy(self, newMainEnemy):
        self.__mainEnemy = newMainEnemy
    def changeMissionRewards(self, newMissionRewards):
        self.__missionRewards = newMissionRewards
    def changeOtherDetails(self, newOtherDetails):
        self.__otherDetails = newOtherDetails


def startMenu():
    testForFile()
    print("1) View all my characters")
    print("2) Create a new mission")
    print("3) Search for a mission")
    print("4) Change a mission")
    print("5) View detailed mission information")
    print("6) Exit")
    action = eval(input("Welcome to the character builder! What would you like to do? "))
    if action == 1:
        table()
        startMenu()
    elif action == 2:
        missionMaker()
        startMenu()
    elif action == 3:
        name = input("What mission are you looking for? ").lower()
        missionSearch(name)
        startMenu()
    elif action == 4:
        name = input("What mission do you want to change? ")
        change = input("Do you want to change the name, quest line, type, starting location, starting NPC, key items, outline, destination, enemy, reward, or other details? ").lower()
        missionEditor(name, change)
        startMenu()
    elif action == 5:
        name = input("Which mission do you want to see the full details of? ")
        missionDetails(name)
        startMenu()
    elif action == 6:
        print("Bye!")
    else:
        print("Not a valid entry, please try again. Mission names are case sensitive.")
        startMenu()


### Tests to see if desired file exists, creates it if not ###
def testForFile():
    try:
        infile = open("Python/Mission Maker/Mission_Creator.txt", 'r')
    except FileNotFoundError:
        fileCreator = open("Python/Mission Maker/Mission_Creator.txt", 'w+')
        print("This file didn't exist, but now it does! Try creating a new mission!")
        missionMaker()
        startMenu()
    infile.close


### Opens an existing file to read created characters from and creates a list of them ###
def openForReading():
    missionList = []
    nameSentinel = ""
    infile = open("Python/Mission Maker/Mission_Creator.txt", 'r')
    missionName = infile.readline().strip()
    if missionName == "":
        infile.close()
        print("It looks like you don't have any missions in there, try making one!")
        missionMaker()
        infile = open("Python/Mission Maker/Mission_Creator.txt", 'r')
        missionName = infile.readline().strip()        
    while missionName != nameSentinel :
        missionType = infile.readline().strip()
        questLine = infile.readline().strip()
        startingPoint = infile.readline().strip()
        startingNPC =  infile.readline().strip()
        keyItems = infile.readline().strip()
        missionOutline = infile.readline().strip()
        missionDestination = infile.readline().strip()
        mainEnemy = infile.readline().strip()
        missionRewards = infile.readline().strip()
        otherDetails = infile.readline().strip()
        missionList.append(Mission(missionName, missionType, questLine, startingPoint, startingNPC, keyItems, missionOutline, missionDestination, mainEnemy, missionRewards, otherDetails))
        missionName = infile.readline().strip()      
    infile.close
    return missionList


### Replaces a specific line of text in the file ###
def replaceLine(lineNumber, text):
    fileName = "Python/Mission Maker/Mission_Creator.txt"
    linesRead = open(fileName, 'r+').readlines()
    linesRead[lineNumber] = (text + "\n")
    out = open(fileName, 'w+')
    out.writelines(linesRead)
    out.close()


### Reads file to find total number of lines in the file ###
def findTotalNumberOfLines():
    testForFile()
    nameSentinel = ""
    counter = 0
    infile = open("Python/Mission Maker/Mission_Creator.txt", 'r')
    reader = infile.readline()
    while reader != nameSentinel :
        reader = infile.readline()
        counter += 1
    infile.close()
    return counter


### Finds lines to a specific character in the file ###
def findLinesToMission(missionName):
    nameSentinel = str(missionName)
    counter = 0
    infile = open("Python/Mission Maker/Mission_Creator.txt", 'r')
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
    openFile = open("Python/Mission Maker/Mission_Creator.txt", 'a+')
    if newFile == 1:
        openFile.write(listName[i].getMissionName())
        openFile.write("\n")
        openFile.write(listName[i].getStartingPoint())
        openFile.write("\n")
        openFile.write(listName[i].getQuestLine())
        openFile.write("\n")
        openFile.write(listName[i].getStartingNPC())
        openFile.write("\n")
        openFile.write(listName[i].getMissionType())
        openFile.write("\n")        
        openFile.write(listName[i].getKeyItems())
        openFile.write("\n")
        openFile.write(listName[i].getMissionOutline())
        openFile.write("\n")
        openFile.write(listName[i].getMissionDestination())
        openFile.write("\n")
        openFile.write(listName[i].getMainEnemy())
        openFile.write("\n")
        openFile.write(listName[i].getMissionRewardse())
        openFile.write("\n")
        openFile.write(listName[i].getOtherDetails())
    else:
        openFile.write(listName[i].getMissionName())
        openFile.write("\n")
        openFile.write(listName[i].getMissionType())
        openFile.write("\n")
        openFile.write(listName[i].getQuestLine())
        openFile.write("\n")
        openFile.write(listName[i].getStartingPoint())
        openFile.write("\n")
        openFile.write(listName[i].getStartingNPC())
        openFile.write("\n")
        openFile.write(listName[i].getKeyItems())
        openFile.write("\n")
        openFile.write(listName[i].getMissionOutline())
        openFile.write("\n")
        openFile.write(listName[i].getMissionDestination())
        openFile.write("\n")
        openFile.write(listName[i].getMainEnemy())
        openFile.write("\n")
        openFile.write(listName[i].getMissionRewards())
        openFile.write("\n")
        openFile.write(listName[i].getOtherDetails())
        openFile.write("\n")
    openFile.close

    
def table():
    missionList = openForReading()
    print("-" *150)
    print(('{:<35}'.format('Mission Name')),('{:<20}'.format('Mission Type')), ('{:<40}'.format('Quest Line')), ('{:<25}'.format('Starting Point')), ('{:<25}'.format('Main Enemy')))
    print("-" *150)
    for i in range(len(missionList)):
        print(format(missionList[i].getMissionName(), "35s"),format(missionList[i].getMissionType(), "20s"), format(missionList[i].getQuestLine(), "40s"), format(missionList[i].getStartingPoint(), "25s"), missionList[i].getMainEnemy(), "\t")
    print("-" * 150)


def missionMaker():
    missionName = input("What is the name of this mission? ")
    missionType = input("What is the mission type (contract, find item, task to complete, etc.)? ")
    questLine = input("Is this part of a larger quest line, or a sub mission? If so, which one? ")
    startingPoint = input("Where does the mission start? ")
    startingNPC = input("What NPC needs to be spoken to to begin the quest? ")
    keyItems = input("What key items are given or required for the quest? ")
    missionOutline = input("Give a short outline of the mission: ")
    missionDestination = input("Where is the final destination for the mission ")
    mainEnemy = input("Who is the main enemy? You can add stats in the other section. ")
    missionRewards = input("What rewards does the party get upon completion? ")
    otherDetails = input("Feel free to add any additional details about the mission: ")

    newMissionList = []
    newMissionList.append(Mission(missionName, missionType, questLine, startingPoint, startingNPC, keyItems, missionOutline, missionDestination, mainEnemy, missionRewards, otherDetails))
    i = 0
    fileWriting(0,newMissionList,i)
    print("Mission", missionName, "added successfully!")
    print("")

    
def missionEditor(name, change):
    missionList = openForReading()

    if change == "name":
        i = 0
        j = 0
        # j is the number of lines below the mission name the desired information is at
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break

            if missionList[i].getMissionName() == name:
                newMissionName = input("What would you like the name of the mission to be? ")
                missionList[i].changeMissionName(newMissionName)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getMissionName())
    elif change == "type":
        i = 0
        j = 1
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newMissionType = input("What would you like the type of mission to be? ")
                missionList[i].changeMissionType(newMissionType)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getMissionType())
    elif change == "quest line":
        i = 0
        j = 2
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newQuestLine = input("Is this a part of another quest line or a sub mission? If so, which one? ")
                missionList[i].changeQuestLine(newQuestLine)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getQuestLine())
    elif change == "starting location":
        i = 0
        j = 3
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newStartingPoint = input("Where do you want the mission to start? ")
                missionList[i].changeStartingPoint(newStartingPoint)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getStartingPoint())
    elif change == "starting npc":
        i = 0
        j = 4
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newStartingNPC = input("What would you like the name of the mission to be? ")
                missionList[i].changeStartingNPC(newStartingNPC)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getStartingNPC())
    elif change == "key items":
        i = 0
        j = 5
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newKeyItems = input("Please enter all the items required for this mission: ")
                missionList[i].changeKeyItems(newKeyItems)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getMissionName())
    elif change == "outline":
        i = 0
        j = 6
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newMissionOutline = input("Please enter the new outline for the mission: ")
                missionList[i].changeMissionOutline(newMissionOutline)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getMissionOutline())
    elif change == "destination":
        i = 0
        j = 7
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newMissionDestination = input("Where is the new mission destination? ")
                missionList[i].changeMissionDestination(newMissionDestination)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getMissionDestination())
    elif change == "enemy":
        i = 0
        j = 8
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newMainEnemy = input("Please enter all the information for the main enemy: ")
                missionList[i].changeMainEnemy(newMainEnemy)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getMainEnemy())
    elif change == "reward":
        i = 0
        j = 9
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newMissionRewards = input("What rewards will the party now receive? ")
                missionList[i].changeMissionRewards(newMissionRewards)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getMissionRewards())
    elif change == "other details":
        i = 0
        j = 10
        findLinesToMission(name)
        k = findLinesToMission(name)
        l = j + k
        while i in range(len(missionList)):
            if k == False:
                print("Couldn't find that mission, check your spelling and case.")
                break
            if missionList[i].getMissionName() == name:
                newOtherDetails = input("Enter all of you additional details: ")
                missionList[i].changeOtherDetails(newOtherDetails)
                break
            else:
                i += 1
        replaceLine(l, missionList[i].getMissionRewards())
    else:
        print("Sorry, that isn't an option. Going back to the main menu.")

def missionSearch(name):
    missionList = openForReading()
    confirmNameExists = findLinesToMission(name)
    i = 0
    while i in range(len(missionList)):
        if missionList[i].getMissionName() == name:
            print("-" *150)
            print(('{:<35}'.format('Mission Name')),('{:<20}'.format('Mission Type')), ('{:<40}'.format('Quest Line')), ('{:<25}'.format('Starting Point')), ('{:<25}'.format('Main Enemy')))
            print("-" *150)
            print(format(missionList[i].getMissionName(), "35s"),format(missionList[i].getMissionType(), "20s"), format(missionList[i].getQuestLine(), "40s"), format(missionList[i].getStartingPoint(), "25s"), missionList[i].getMainEnemy(), "\t")
            print("-" * 150)
            break
        elif confirmNameExists == False:
            print("Couldn't find that mission, check your spelling and case.")
            break
        else:
            i += 1


def missionDetails(name):
    missionList = openForReading()
    confirmNameExists = findLinesToMission(name)
    i = 0
    while i in range(len(missionList)):
        if missionList[i].getMissionName() == name:
            print("Mission Name")
            print("-" *15)
            print(missionList[i].getMissionName())
            print("\n")
            print("Mission Type")
            print("-" *15)
            print(missionList[i].getMissionType())
            print("\n")
            print("Quest Line")
            print("-" *15)
            print(missionList[i].getQuestLine())
            print("\n")
            print("Starting Point")
            print("-" *15)
            print(missionList[i].getStartingPoint())
            print("\n")
            print("Starting NPC")
            print("-" *15)
            print(missionList[i].getStartingNPC())
            print("\n")
            print("Key Items")
            print("-" *15)
            print(missionList[i].getKeyItems())
            print("\n")
            print("Mission Outline")
            print("-" *15)
            print(missionList[i].getMissionOutline())
            print("\n")
            print("Mission Destination")
            print("-" *15)
            print(missionList[i].getMissionDestination())
            print("\n")
            print("Main Enemy")
            print("-" *15)
            print(missionList[i].getMainEnemy())
            print("\n")
            print("Mission Rewards")
            print("-" *15)
            print(missionList[i].getMissionRewards())
            print("\n")
            print("Other Details")
            print("-" *15)
            print(missionList[i].getOtherDetails())
            print("\n")
            break
        elif confirmNameExists == False:
            print("Couldn't find that mission, check your spelling and case.")
            break
        else:
            i += 1

            
startMenu()


                          
