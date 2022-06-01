import random

import random

#Rolls a certian number sided dice
def diceRoll(num):

    roll = random.randint(1 , num)

    #print("The roll was: ", roll)

    return roll

############
print("")
############

#Generates a dungeon with a number of rooms based on the dice and roll
def generateDungeon():
    diceRoll(6)
    
    numberOfRooms = diceRoll(6)

    #print("The roll was: ", roll6)
    
    if numberOfRooms > 1:
        print("There are ", numberOfRooms, "rooms in this dungeon.")

    else:
        print("There is only 1 room in this dungeon.")

    return numberOfRooms

############
print("")
############

#Defines the size and events of a room the players enter
def randomRoom():
    diceRoll(4)

    numberOfRooms = generateDungeon()

    roomSize = diceRoll(4)
    
    while numberOfRooms != 0:

        #print("The roll was: ", roll4)
        
        if roomSize == 1:
            print("You comebto a small room")
            enemyInRoom()
            chanceOfChest()
            

        elif roomSize == 2:
            print("You come to a normal sized room")
            enemyInRoom()
            chanceOfChest()
            
        else:
            
            if roomSize == 3 or roomSize == 4:

                diceRoll(10)
        
                largeRoom = diceRoll(10)
           
                if largeRoom <= 5:
                    print("You come to a normal sized room")
                    enemyInRoom()
                    chanceOfChest()
                else:
                    print("You come to a large room")
                    enemyInRoom()
                    chanceOfChest()

        numberOfRooms -= 1


############
print("")
############


#Defines the chance of finding a chest in a room
def chanceOfChest():
    diceRoll(20)

    chestChance = diceRoll(20)

    #print("The roll was: ", chestChance)

    if chestChance >= 17:
        findAChest()
        
    elif chestChance == 1:
        print("You find a chest and decide to look inside... It's a mimic!")
        print("")
        print("After battle, you continue on")
        
    else:
        print("There appears to be nothing of value in this room.")
        

############
print("")
############


#Defines the chance of obtaining certain items in a chest
def findAChest():
    diceRoll(20)
    
    roll = diceRoll(20)
    gold = diceRoll(20) * .75
    platinum = diceRoll(20) * .5
    emperium = diceRoll(20) * .1
    
    foundChest = input("You've found a chest! Would you like to open it? ")

    if foundChest == "yes" or foundChest == "Yes":
        
        #print("The roll was: ", roll20)

        if roll == 1:
            print("The chest is a mimic! Prepare for battle!")
            
            
        elif roll < 15:
            print("Sadly, the chest is empty. You move on from the chest.")
            
        
        elif roll < 18:
            
            print("You find ", format(gold, "3.0f"), "Gold in the chest!")

            lookAgain = input("Would you like to look again? ")
        
            if lookAgain == "yes" or foundChest == "yes":

                diceRoll(20)
                
                if roll == 20:

                    #print("The roll was: ", roll20)
                
                    print("You find ", format(gold, "3.0f"), " more Gold in the chest!")

                else:
                    print("You don't see anything else and move on from the chest.")

        elif roll < 19:
            
            print("You find ", format(platinum, "3.0f"), "Platinum in the chest!")

            lookAgain = input("Would you like to look again? ")
        
            if lookAgain == "yes" or foundChest == "yes":

                diceRoll(20)
                
                if roll == 20:

                #print("The roll was: ", roll20)
                
                    print("You find ", format(gold, "3.0f"), " more Gold in the chest!")

                else:
                    print("You don't see anything else and move on from the chest.")


            
        elif roll < 20:
            
            print("You find ", format(emperium, "3.0f"), "Emperium in the chest!")


            lookAgain = input("Would you like to look again? ")
        
            if lookAgain == "yes" or foundChest == "yes":

                diceRoll(20)
                
                if roll == 20:

                #print("The roll was: ", roll20)
                
                    print("You find ", format(gold, "3.0f"), " more Gold in the chest!")

                else:
                    print("You don't see anything else and move on from the chest.")

        else:

            diceRoll(20)

            if roll >= 17:

                print("You find a magical item in the chest!")
    print("")
             
        
    if foundChest == "No" or foundChest == "no":
        print("You move on and leave the chest behind.")

    print("")
    
#################
print("")
#################

#Determines if enemies are in a room and how many
def enemyInRoom():
    diceRoll(20)

    enemyAppears = diceRoll(20)

    diceRoll(6)

    numberOfEnemies = diceRoll(6)

    if enemyAppears == 1:
        print("You walk into the room and it appears to be empty.", end="")
        print("Then you hear the door close behind you. ", end="")
        print("You turn to find", numberOfEnemies + 2 , "enemies waiting in ambush!")
        print("")
        print("After defeating the enemies the room appears to be safe.")
        print("")
        
        searchRoom = input("Do you want to search the room? ")

        if searchRoom == "yes" or searchRoom == "Yes":
            chanceOfChest
            
        else:
            print("You decide to move on from this room")
        

    elif enemyAppears < 15:
        print("You open the door to find", numberOfEnemies, "enemies!")
        print("")
        print("After defeating the enemies the room appears to be safe.")
        print("")
        
        searchRoom = input("Do you want to search the room? ")

        if searchRoom == "yes" or searchRoom == "Yes":
            chanceOfChest
            
        else:
            print("You decide to move on from this room")

    else:
        print("This room appears to be safe.")
        
        searchRoom = input("Do you want to search the room? ")

        if searchRoom == "yes" or searchRoom == "Yes":
            chanceOfChest
            
        else:
            print("You decide to move on from this room")

#Runs program and has each section commented out for troubleshooting
def dungeon():
#diceRoll(20)
#findAChest()
#generateDungeon()
    randomRoom()
#chanceOfChest()
#enemyInRoom()

if __name__ == '__main__':
    dungeon()

#Commented out print statements are for troubleshooting and confirming
#that the rolls and results are giving correct outputs

