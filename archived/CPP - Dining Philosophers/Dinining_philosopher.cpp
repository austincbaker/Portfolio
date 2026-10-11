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

void Dining_Philosopher(){
        s = new Statistics();
        printf("Thinking about starting Philosopher's Table...\n");
        philosopher();
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
        }
    }
}
