// 
// 
// 
// 
// This code will require the NachOS platform to run properly
// 
// 
// 
// 


#include <cassert>
#include <valarray>
#include <semaphore.h>
#include "system.h"
#include "synch.h"

#define BUFFERMAX 9999

Statistics *s;
int ready = 0;
Thread *t;
int functionSelect;
int seedValue;

void mailboxInit();
void postoffice(int);
int numPeople;
int maxMessages;
int msgSent = 0;
int boxCapacity;
char ***mailbox = new char **[numPeople];
char msgs[5][50]{
        "I am the Walrus", "The cake is a lie",
        "Kilroy was here", "Drink More Ovaltine", 
        "This Message Never Existed",
};
Semaphore *emptySlots = new Semaphore("Counts Empty Spaces", 1);
Semaphore *fullSpaces = new Semaphore("Counts filled Spaces", 1);
Semaphore *mailboxMutex = new Semaphore("Mailbox Mutex", 1);



void mailboxInit() {
    printf("The Post Office} Problem \n");
    printf("How many people? \n");
    numPeople = 10;
    printf("How many messages can each mailbox hold? \n");
    boxCapacity = 5;
    printf("How many messages can be sent? \n");
    maxMessages = 50;

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