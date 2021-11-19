class Employee:
    
    def __init__(self,nameIn,hoursIn,rateIn):
        self.__name = nameIn
        self.__hours = hoursIn
        self.__rate = rateIn
        
    def GetName(self):
        return self.__name
    
    def GetHours(self):
        return self.__hours
    
    def GetRate(self): 
        return self.__rate
    
    def GetGrossPay(self):
        return self.__hours * self.__rate


def menu():

    employeeList = main()

    startup = input("Would you like to access the main menu? (yes or no) ")

    while startup == "yes":
        print("1) Display Employee Information Table")
        print("2) Query Employee Information")
        print("3) Display Employee with Min/Max Gross Pay")
        print("4) Exit")

        print("")

        menuOption = eval(input("Which function would you like to preform? "))

        print("")
        
        if menuOption == 1:
            table()
    
        elif menuOption == 2:
            num = eval(input("Enter employee ID: "))
            print("-" *50)

            print("Employee\t\tHours\t Rate\t     Pay")

            print("-" *50)

            print(format(employeeList[num].GetName(), "20s"),format(employeeList[num].GetHours(), "6.0f"), "    " ,format(employeeList[num].GetRate(), "5.2f"), '\t' , format(employeeList[num].GetGrossPay(), "9.2f"))
                       
        elif menuOption == 3:
           minMaxPay()

        elif menuOption == 4:
            print("Goodbye!")
            break
        
        else:
           print("Sorry that's not a valid choice, please try again.")
           print("")

    if startup == "no":
        print("Goodbye!")

    

def main():
    infileName = open("names.py", 'r')
    infileRates = open("rates.py", 'r')
    infileHours = open("hours.py", 'r')

    name = infileName.readline().strip()
    rate = eval(infileRates.readline())
    hours = eval(infileHours.readline())

    employeeList = []

    num = 1

    while rate != -99.99:

        worker = Employee(name,hours,rate)

        employeeList.append(worker)

        name = infileName.readline().strip()
        hours = eval(infileHours.readline())
        rate = eval(infileRates.readline())

        num =+ 1

    return employeeList

def table():

    employeeList = main()
    
    print("-" *50)

    print("Employee\t\tHours\t Rate\t     Pay")

    print("-" *50)

    for i in range(len(employeeList)):

        print(format(employeeList[i].GetName(), "20s"),format(employeeList[i].GetHours(), "6.0f"), "    " ,format(employeeList[i].GetRate(), "5.2f"), '\t' , format(employeeList[i].GetGrossPay(), "9.2f"))

    
    print("-" * 50)

def minMaxPay():

    employeeList = main()
    
    loc = 0

    maximum = employeeList[0].GetGrossPay()

    for i in range(len(employeeList)):

        if employeeList[i].GetGrossPay() > maximum:
            maximum = employeeList[i].GetGrossPay()
            loc = i

    print("-" *50)

    print("Employee\t\tHours\t Rate\t     Pay")

    print("-" *50)

    print(format(employeeList[loc].GetName(), "20s"),format(employeeList[loc].GetHours(), "6.0f"), "    " ,format(employeeList[loc].GetRate(), "5.2f"), '\t' , format(employeeList[loc].GetGrossPay(), "9.2f"))

    print("")

    minimum = employeeList[0].GetGrossPay()

    for j in range(len(employeeList)):

        if employeeList[j].GetGrossPay() < minimum:
            minimum = employeeList[j].GetGrossPay()
            loc = j

    print("-" *50)

    print("Employee\t\tHours\t Rate\t     Pay")

    print("-" *50)

    print(format(employeeList[loc].GetName(), "20s"),format(employeeList[loc].GetHours(), "6.0f"), "    " ,format(employeeList[loc].GetRate(), "5.2f"), '\t' , format(employeeList[loc].GetGrossPay(), "9.2f"))

    print("")
    
menu()


        

    
    




