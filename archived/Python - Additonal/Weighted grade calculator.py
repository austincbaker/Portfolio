#Calculate the weighted homework grade, pog is percent of grade
def homeWork(num):

    hwGrade = 0

    hwPointsPoss = 0

    for i in range(num):

        addHwGrade = eval(input("How many points did you get? "))
        
        print("")

        addHwPointsPoss = eval(input("How many points were possible? "))

        print("")
        
        hwGrade += addHwGrade
        
        hwPointsPoss += addHwPointsPoss
        
        #print(hwGrade , hwPointsPoss)

    POG = eval(input("Please enter the percentage of your grade HW is worth: "))

    print("")
    
    #print(POG)
    
    weight = POG / 100
    #print(weight)

    totals = hwGrade / hwPointsPoss
    #print(totals)

    weightedTotal = totals * weight
    #print(weightedTotal)

    weightedHwGrade = weightedTotal

    return weightedHwGrade

    
#Calculate the weighted quiz grade, pog is percent of grade
def quizzes(num):

    quizGrade = 0

    quizPointsPoss = 0

    for i in range(num):

        addQuizGrade = eval(input("How many points did you get? "))
        
        print("")

        addQuizPointsPoss = eval(input("How many points were possible? "))

        print("")
        
        quizGrade += addQuizGrade
        
        quizPointsPoss += addQuizPointsPoss
        
        #print(quizGrade , quizPointsPoss)

    POG = eval(input("Please enter the percentage of your grade quizzes are worth: "))

    print("")
    
    #print(POG)
    
    weight = POG / 100
    #print(weight)

    totals = quizGrade / quizPointsPoss
    #print(totals)

    weightedTotal = totals * weight
    #print(weightedTotal)

    weightedQuizGrade = weightedTotal

    return weightedQuizGrade


#Calculate the weighted test grade, pog is percent of grade
def tests(num):
       
    testGrade = 0

    testPointsPoss = 0

    for i in range(num):

        addTestGrade = eval(input("How many points did you get? "))
        
        print("")

        addTestPointsPoss = eval(input("How many points were possible? "))

        print("")
        
        testGrade += addTestGrade
        
        testPointsPoss += addTestPointsPoss
        
        #print(testGrade , testPointsPoss)

    POG = eval(input("Please enter the percentage of your grade tests are worth: "))

    print("")
    
    #print(POG)
    
    weight = POG / 100
    #print(weight)

    totals = testGrade / testPointsPoss
    #print(totals)

    weightedTotal = totals * weight
    #print(weightedTotal)

    weightedTestGrade = weightedTotal

    return weightedTestGrade


#Calculate the weighted additional section grades, pog is percent of grade

def additionalSections(numOfSect):

    sectionGradeList = []
           
    grade = 0

    pointsPoss = 0

    for i in range(numOfSect):

        numOfGrades = eval(input("How many grades do you have in this section? "))

        print("")
    
        for j in range(numOfGrades):                  

            addGrade = eval(input("How many points did you get? "))
            
            print("")

            addPointsPoss = eval(input("How many points were possible? "))

            print("")
            
            grade += addGrade
            
            pointsPoss += addPointsPoss
            
            #print(grade , pointsPoss)

        POG = eval(input("Please enter the percentage of your grade this section is worth: "))

        print("")
    
        #print(POG)
        
        weight = POG / 100
        #print(weight)

        totals = grade / pointsPoss
        #print(totals)

        weightedTotal = totals * weight
        #print(weightedTotal)

        sectionGradeList.append(weightedTotal)

        #print(sectionGradeList)

    
    additionalWeightedGrades = sum(sectionGradeList)

    return additionalWeightedGrades

         
#Calculate the weighted final exam grade, pog is percent of grade
def finalExam():
    POG = eval(input("Please enter the percentage of your grade the final exam is worth: "))

    print("")

    grade = eval(input("How many points did you get? "))

    print("")

    pointsPoss = eval(input("How many points were possible? "))

    weight = POG / 100

    totals = grade / pointsPoss

    weightedTotal = totals * weight

    weightedFinalGrade = weightedTotal

    return weightedFinalGrade        

def main():

    print("To save time if you are trying to figure out what you need on the final exam to pass, total up all of your points for each section and just enter as if you had one big assignment.")

    print("")

    print("")

    print("")

#############
    
    startHw = input("Do you have homework grades to enter? ").lower()

    print("")
    
    if startHw == "yes":
        num = eval(input("How many do you have to enter? "))
        
        print("")
    
        hw = homeWork(num)
        
    else:
        hw = 0

############

    startQuiz = input("Do you have quiz grades to enter? ").lower()

    print("")
    
    if startQuiz == "yes":
        num = eval(input("How many do you have to enter? "))
            
        print("")
    
        quiz = quizzes(num)
        
    else:
        quiz = 0

#############
        
    startTest = input("Do you have test grades to enter? ").lower()

    print("")
    
    if startTest == "yes":
        num = eval(input("How many do you have to enter? "))
    
        print("")
    
        test = tests(num)
        
    else:
        test = 0

###########
        
    startAddSections = input("Do you have additional section grades to enter? ").lower()

    print("")
    
    if startAddSections == "yes":
        numOfSect = eval(input("How many sections do you have to enter? "))
        
        print("")
    
        addSections = additionalSections(numOfSect)
        
    else:
        addSections = 0

#########
        
    startFinal = input("Do you have a Final Exam grade to enter? ").lower()

    print("")
    
    if startFinal == "yes":
        final = finalExam()
        
    else:
        final = 0

        
    overallGrade = (hw + quiz + test + addSections + final) * 100


    print("")
    
    print("Your overall grade is: ", format(overallGrade, "2.2f"), "%")

main()




    
