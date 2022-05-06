#include <semaphore.h>
#include "system.h"
#include "synch.h"

Statistics *s;
int ready = 0;
Thread *t;
int functionSelect;
int seedValue;

void philosopher();
void holder(int, int);
void restaurant(int);
int numPhilo;
int numMeals;
bool *chopsticks = new bool{true};
bool *arrived = new bool{false};
int initMeals;
Semaphore **mySemaphores;
Semaphore *mealSem = new Semaphore("Meal", 1);



void mailboxInit();
void postoffice(int);
int numPeople;
int maxMessages;
int msgSent = 0;
int boxCapacity;
char ***mailbox = new char **[numPeople];
char msgs[5][50]{
        "I am the Walrus", "The cake is a lie",
        "Kilroy was here", "Drink More Ovaltine", "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
};
Semaphore *emptySlots = new Semaphore("Counts Empty Spaces", 1);
Semaphore *fullSpaces = new Semaphore("Counts filled Spaces", 1);
Semaphore *mailboxMutex = new Semaphore("Mailbox Mutex", 1);


void *read(int);
void *write(int);
void readersWriters(int);
int numReaders;
int numWriters;
int readCount = 0;
int readersPerFile;
int totalReaders = 0;
int stopRead = numReaders;
int stopWrite = numWriters;
Semaphore *semMutex = new Semaphore("Semaphore Mutex", readersPerFile);
Semaphore *semArea = new Semaphore("Semaphore Barrier", readersPerFile);
Semaphore *writerBlock = new Semaphore("Writer Barrier", 0);
Semaphore *writeWait = new Semaphore("Writer Staging", 0);


int readAndClean();

void printTable();

void ThreadTest() {
    DEBUG('t', "Entering ThreadTest");
   
    if(functionSelect > 3 || functionSelect < 1){
        printf("Please only enter 1,2, or 3 to select a program to run.");
        Cleanup();
    }

    if (functionSelect == 1) {
        s = new Statistics();
        printf("Thinking about starting Philosopher's Table...\n");
        philosopher();

    } else if (functionSelect == 2) {
        printf("Post Office Problem\n");
        mailboxInit();
    } else if (functionSelect == 3) {
        semArea = new Semaphore("Semaphore Area", 1);
        semMutex = new Semaphore("Semaphore Mutex", 1);
        t = new Thread("readersWriters");
        t->Fork(readersWriters, 0);
    }
}

void philosopher() {
    printf("The Philosopher Problem \n");
    printf("How many Philosophers? \n");
    numPhilo = readAndClean();
    printf("How many meals are being served? \n");
    numMeals = readAndClean();
    printf("%d Philos and %d Meals. \n", numPhilo, numMeals);
    initMeals = numMeals;


    mySemaphores = new Semaphore*[numPhilo];
    for (int i = 0; i < numPhilo; i++) {
        // Allocate memory for semaphore, init to 1
        mySemaphores[i] = new Semaphore("Philo Semaphore", 1);
    }

    arrived = &arrived[numPhilo];
    for (int i = 0; i < numPhilo; i++) {
        arrived[i] = 0;
    }

    chopsticks = &chopsticks[numPhilo];
    for (int i = 0; i < numPhilo; i++) {
        chopsticks[i] = 1;
    }

    Thread *p;
    for (int i = 0; i < numPhilo; i++) {
        p = new Thread("Philosopher");
        p->Fork(restaurant, i);
    }
}

void holder(int num, int stage) {
    if (stage == 0) {
        arrived[num] = true;
        printf("Philo %d has arrived.\n", num);
        int i = 0;
        while (i < numPhilo) {
            if (arrived[i]) {
                i++;
                currentThread->Yield();
            }
        }
        //semArea->V();
    }

    if (stage == 1) {
        arrived[num] = true;
        printf("Philo %d is ready to leave..\n", num);
        int i = 0;
        while (i < numPhilo) {
            if (arrived[i]) {
                i++;
            }
            currentThread->Yield();
        }
        printf("All Philosophers have left the table.\n");
        printTable();
        currentThread->Finish();
    }
}

void restaurant(int num) {
    holder(num, 0);
    printf("All the philosophers have arrived and take a seat.\n");

    int left = ((num + 1) % numPhilo);
    int right = num;
    printf("philo %d is checking chopsticks \n", num);

    while (numMeals > 0) {
        if (numMeals < 1) {
            printf("Philo %d sees there is no food left, and drops the chopsticks then waits to leave.\n", num);
            chopsticks[right] = true;
            chopsticks[left] = true;
            arrived[num] = 0;
            holder(num, 1);
        }
        printf("philo %d is checking chopsticks \n", num);
        mySemaphores[right]->P();
        //currentThread->Yield();
        printf("philo %d has picked up the right chopstick \n", num);
        mySemaphores[left]->P();
        printf("philo %d has picked up the left chopstick\n", num);
        if (chopsticks[right] && chopsticks[left]) {
            chopsticks[right] = false;
            chopsticks[left] = false;
            printf("Philo %d picks up left and right chopsticks ad begins eating\n", num);

            int randNum = Random() % 3 + 3;
            int i = 0;
            while (i < randNum) {
                if (numMeals < 1) {
                    printf("Philo %d sees there is no food left, and drops the chopsticks then waits to leave.\n", num);
                    chopsticks[right] = true;
                    chopsticks[left] = true;
                    arrived[num] = 0;
                    holder(num, 1);
                } else {
                    numMeals--;
                    i++;
                    printf("Philo %d eats a meal, %d meals remaining\n", num, numMeals);
                }

                chopsticks[left] = true;
                chopsticks[right] = true;
                mySemaphores[right]->V();
                printf("Philo %d sets down the right chopstick.\n", num);
                mySemaphores[left]->V();
                printf("Philo %d sets down the left chopstick.\n", num);

            }
             randNum = Random() % 3 + 3;
             i = 0;
            while (i < randNum) {
                printf("Philo %d is thinking.... \n", num);
                i++;
            }
            printf("Philo %d is done thinking....\n", num);
            if (numMeals < 1) {
                holder(num, 1);
            }
            //currentThread->Yield();
        }
    }
}

void mailboxInit() {
    printf("The Post Office} Problem \n");
    printf("How many people? \n");
    numPeople = readAndClean();
    printf("How many messages can each mailbox hold? \n");
    boxCapacity = readAndClean();
    printf("How many messages can be sent? \n");
    maxMessages = readAndClean();

    // Allocate 3D array of char pointers
    // Dim1 = Person; Dim2 = Slot; Dim3 = Slot Message
    mailbox = new char **[numPeople];
    for (int i = 0; i < numPeople; i++) {  // For each person
        // Now we allocate space for each person’s mailboxes
        mailbox[i] = new char *[boxCapacity];
        for (int j = 0; j < boxCapacity; j++) {  // For each slot
            // Slot size should be big enough your messages
            mailbox[i][j] = new char[50];
        }
    }

    Thread *p;
    for (int i = 0; i < numPeople; i++) {
        p = new Thread("Patron");
        p->Fork(postoffice, i);
    }
    printf("%d\n", (Random() % 5));


}

void postoffice(int num) {
    printf("Persom %d is in the post office\n", num);
    while (msgSent != maxMessages) {
        printf("\tPersom %d is Checking their box\n", num);
        int i = 0;
        while (i < boxCapacity) {
            mailboxMutex->P();
            if (strlen(mailbox[num][i]) < 1) {
                printf("\t\tPerson %d slot %d is empty\n", num, i);
                i++;
                mailboxMutex->V();
            } else if (strlen(mailbox[num][i]) > 1) {
                if (msgSent == maxMessages) {
                    break;
                }
                fullSpaces->P();
                printf("\t\t\tPersom %d letter reads: %s\n", num, mailbox[num][i]);
                mailbox[num][i] = new char[50];
                printf("\t\t\t\tPersom %d Has another empty slot\n", num);
                fullSpaces->V();
                mailboxMutex->V();
                i = 0;
                currentThread->Yield();
            }
        }
        int randBox = Random() % numPeople;
        while(randBox == num){
            randBox = Random() % numPeople;
        }
        int randMsg = Random() % 5;

        printf("\t\t\t\t\tPerson %d is writing a letter to "
               "person %d\n", num, randBox);
        i = 0;
        while (i < boxCapacity) {
            if (msgSent == maxMessages) {
                break;
            }
            if (strlen(mailbox[randBox][i]) < 1) {
                emptySlots->P();
                msgSent++;
                printf("Total Messages Sent: %d\n", msgSent);
                mailbox[randBox][i] = msgs[randMsg];
                emptySlots->V();
                break;
            } else {
                i++;
                if (i == boxCapacity) {
                    i = 0;
                    randBox = Random() % numPeople;
                    randMsg = Random() % 5;
                }
            }
        }

        //  add the item to the  buffer
        printf("Person %d has left the post office\n", num);
        int randNum = Random() % 3 + 3;
        for (int i = 0; i < randNum; i++) {
            printf("Person %d is wandering aimlessly...\n", num);
            currentThread->Yield();
        }
    }int j = 0;
    currentThread->Yield();
    printf("\nStarting end sequence for person %d\n", num);
    for (int j = 0; j < boxCapacity; j++) {
        if (strlen(mailbox[num][j]) < 1) {
            printf("Person %d slot %d is empty\n", num, j);
            j++;
        } else {
            fullSpaces->P();
            printf("Persom %d letter reads: %s\n", num, mailbox[num][j]);
            mailbox[num][j] = new char[50];
            fullSpaces->V();
        }
        mailboxMutex->V();
    }
}

void *read(int num) {
    semMutex->P();
    readCount++;

    if (readCount < readersPerFile) {
        semArea->P();
    }
    totalReaders++;

    printf("Thread %d is reading.\n", num);
    int randNum = Random() % 3 + 3;
    for (int i = 0; i < randNum; i++) {
    }
    printf("Thread %d is done reading.\n", num);

    readCount--;
    if (readCount == 0) {
        if (totalReaders % readersPerFile == 0) {
            writerBlock->V();
            writeWait->P();
        }
        semArea->V();
    }
    stopRead--;

    if (stopRead == 0) {
        Cleanup();
    }
    semMutex->V();
}


void *write(int num) {
    writerBlock->P();

    printf("Thread %d is writing.\n", num);
    int randNum = Random() % 3 + 3;
    for (int i = 0; i < randNum; i++) {
        //printf("Thread %d is writing for the %d time\n", num, i);
    }
    printf("Thread %d has finished writing.\n", num);

    stopWrite--;

    if (stopWrite == 0) {
        Cleanup();
    }
    writeWait->V();
}

void readersWriters(int num) {
    printf("Readers Writers Problem. Remember, reading is fundamental.\n");
    printf("How many readers? \n");
    numReaders = readAndClean();
    printf("How many writers? \n");
    numWriters = readAndClean();
    printf("How many readers at once? \n");
    readersPerFile = readAndClean();
    printf("%d readers and %d writers. %d readers allowed at once\n", numReaders, numWriters, readersPerFile);

    readCount = 0;
    stopRead = numReaders;
    stopWrite = numWriters;

    Thread *readers;
    Thread *writers;
    int j = 0;
    int a = 0;
    do {
        int k = 0;
        while (k < readersPerFile) {
            readers = new Thread("Reader");
            readers->Fork(VoidFunctionPtr(read), j);
            k++;
            j++;
        }

        if (a < numWriters) {
            writers = new Thread("Writer");
            writers->Fork(VoidFunctionPtr(write), j);
            a++;
        }
    } while (j < (numReaders + numWriters));

}

int cleanEntry(char entry[BUFFERMAX]) {
    auto arg = entry;
    if (strlen(arg) > 9999) {
        printf("\n\n\n Improper argument passed, please enter a smaller number. Exiting...");
        Cleanup();
    }
    if (atoi(arg) > 0) {
        int lenAtoi = floor(log10(abs(atoi(arg)))) + 1;
        if (lenAtoi == strlen(arg)) {
            return atoi(arg);
        } else {
            printf("\n\n\n Improper argument passed. Exiting...");
            Cleanup();
        }
    } else {
        printf("\n\n\n Improper argument passed. Exiting...");
        Cleanup();
    }
}

int readAndClean() {
    char buffer[BUFFERMAX];
    while (true) {
        assert(fgets(buffer, BUFFERMAX, stdin) != NULL);
        // checks that last entery in buffer is \n
        if (buffer[strlen(buffer) - 1] == '\n') {
            // replaced \n with \0 so it prevents error
            buffer[strlen(buffer) - 1] = '\0';
            //printf("%s\n", buffer);
            break;
        }
    }
    return cleanEntry((char *) (buffer));
}

void printTable() {
    printf("The random seed was %d\n", seedValue);
    printf("There were %d number of philosophers\n", numPhilo);
    printf("The number of meals was %d\n", initMeals);

}
