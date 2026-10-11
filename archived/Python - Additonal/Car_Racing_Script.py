import random


class Car:
    def __init__(self, symbolIn):
        self.__location = 0
        self.__symbol = symbolIn

    def GetLocation(self):
        return self.__location

    def GetSymbol(self):
        return self.__symbol

    def MoveCar(self):
        self.__location = self.__location + random.randint(1, 5)

    def DisplayCar(self):
        if (self.__location > 0):
            for i in range(self.__location):
                print('*', end="")
            print("|", self.__symbol)
        else:
            print("|", self.__symbol)


def main():
    go = True
    while (go == True):
        infile = open("lab13_data.py", 'r')

        carList = []
        symbol = (infile.readline()).strip()

        while symbol != '#':
            newCar = Car(symbol)
            carList.append(newCar)
            symbol = (infile.readline()).strip()

        for i in range(5):
            for j in range(len(carList)):
                carList[j].MoveCar()
                carList[j].DisplayCar()

            # pause between each of the 5 "races" of the cars
            x = input("Press <enter> to continue ...")

            print()

        maxLocation = carList[0].GetLocation()
        indexOfMax = 0

        for i in range(len(carList)):
            if carList[i].GetLocation() > maxLocation:
                maxLocation = carList[i].GetLocation()
                indexOfMax = i

        print("Winner: ", carList[indexOfMax].GetSymbol())

        playAgain = input("Play again? (y/n)")
        if(playAgain == "y"):
            go = go
        elif (playAgain == "n"):
            go = not go
        else:
            print("Sorry invalid input")
            break



if __name__ == '__main__':
    main()
