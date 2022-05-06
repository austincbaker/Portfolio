#pragma clang diagnostic push
#pragma ide diagnostic ignored "cert-err58-cpp"
#include "stdint.h"
#include "system.h"
#include "synch.h"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wwritable-strings"

struct ThreadInfo {
    int id;
    int currentBurst;
    int initialBursts;
    int alottedBursts;
};

Lock *lock = new Lock("Lock");
struct ThreadInfo *threadInfo;
struct ThreadInfo *invaderThread;
List *list = new List;

void threadOps(ThreadInfo *threadInfo);
void dispatchFun(int numThreads);
void onCPU(int burstRemaining);
void setInfo(int id);
bool checkNewThread();
void threadInvader(int num);

Semaphore *cpuSem = new Semaphore("CPU Sem", 0);
Semaphore *run = new Semaphore("Run Sem", 0);
Semaphore *dispatchSem = new Semaphore("dispatchSem", 0);
int amountToBurst;
int alottedBurst;//rrBurst; //(Random() % (4 - 1 + 1)) + 1;
int numThreads;
int invaded = 0;
void ThreadTest() {

    if(*projectPart == 1){
        printf("FCFS\n");
    }
    if(*projectPart == 2){
        printf("RR\n");
        alottedBurst == *rrBurst;
    }
    if(*projectPart == 3){
        printf("NSJF\n");
    }
    if(*projectPart == 4){
        printf("PSJF\n");
    }
    numThreads = (Random()%25)+1;
    Thread *task;

    for (int i = 0; i < numThreads; i++) {
        setInfo(i);
        task = new Thread("Task");
        task->Fork(onCPU, amountToBurst);
    }
    printf("Threads to run: %d\n", numThreads);
    Thread *dispatch = new Thread("Dispatcher Thread");
    dispatch->Fork(dispatchFun, numThreads);
}

void threadOps(struct ThreadInfo *threadInfo) {
    run->P();
    printf("Alotted bursts: %d\n",threadInfo->alottedBursts);
    for (int i = 0; i < threadInfo->alottedBursts; i++) {
        if(threadInfo->currentBurst == 0){
            printf("Thread %d has finihsed and is leaving.\n", threadInfo->id);
            break;
        }
            if (*projectPart == 4 && invaded < 4 && threadInfo->currentBurst >0) {
                if(checkNewThread()){
                    invaded++;
                }
            }
        printf("Thread %d Burst %d/%d\n", threadInfo->id, threadInfo->currentBurst, threadInfo->initialBursts);
        threadInfo->currentBurst--;
    }
    dispatchSem->V();
    onCPU(amountToBurst);
}

void threadInvader(int num){
    invaderThread = new ThreadInfo;
    invaderThread->id = Random()%10 + 100;
    invaderThread->initialBursts = (Random() % (50 - 1 + 1)) + 1;
    invaderThread->currentBurst = invaderThread->initialBursts;
    if (*projectPart == 1) {
        invaderThread->alottedBursts = invaderThread->initialBursts;
    }
    if (*projectPart == 2) {
        invaderThread->alottedBursts = *rrBurst;
    }
    if (*projectPart == 3) {
        invaderThread->alottedBursts = invaderThread->initialBursts;
    }
    if (*projectPart == 4) {
        invaderThread->alottedBursts = invaderThread->initialBursts;
    }
    int tempNumThreads = numThreads;
    numThreads = 99;
    dispatchFun(numThreads);
    numThreads = tempNumThreads;
}

bool checkNewThread(){

    int randomChance = Random()%10;
    if( randomChance == 2 || randomChance == 7|| randomChance == 5){
        printf("***A new thread is entering the queue!***\n");
        threadInvader(99);
        return true;
    }
    else{
        return false;
    }

}

void onCPU(int burstTime) {
    cpuSem->P();
    for (int i = 0; i < burstTime; i++) {
        printf("Burst updating\n");
    }
    threadOps(threadInfo);

}

void dispatchFun(int numThreads) {
    if(numThreads == 99){
        if(invaderThread->currentBurst < threadInfo->currentBurst){
            printf("The new thread has less bursts that the thread currently "
                   "on the processor so it is being placed on.\n");
            list->SortedInsert(threadInfo, threadInfo->currentBurst);
            threadInfo->currentBurst = invaderThread->initialBursts;
            threadInfo->id = invaderThread->id;
            return;
        }
        else{
            printf("The new thread has more bursts that the thread currently "
                   "on the processor so it is being placed in the ready queue.\n");
            list->SortedInsert(invaderThread, invaderThread->currentBurst);
            return;
        }
    }
    while(!list->IsEmpty()) {
        cpuSem->V();
        ListElement *x = list->first;
        void *ti = x->item;
        threadInfo = (ThreadInfo*)ti;
        list->Remove();
        run->V();
        dispatchSem->P();
        if(threadInfo->currentBurst != 0){
            if (*projectPart == 3 || *projectPart == 4) {
                list->SortedInsert(threadInfo, threadInfo->currentBurst);
            } else {
                list->Append(threadInfo);
            }
        }
    }
}


void setInfo(int id) {
    threadInfo = new ThreadInfo;
    threadInfo->id = id;
    threadInfo->initialBursts = (Random() % (50 - 1 + 1)) + 1;
    threadInfo->currentBurst = threadInfo->initialBursts;
    if (*projectPart == 1) {
        threadInfo->alottedBursts = threadInfo->initialBursts;
    }
    if (*projectPart == 2) {
        threadInfo->alottedBursts = *rrBurst;
    }
    if (*projectPart == 3) {
        threadInfo->alottedBursts = threadInfo->initialBursts;
    }
    if (*projectPart == 4) {
        threadInfo->alottedBursts = threadInfo->initialBursts;
    }
    if (*projectPart == 3 || *projectPart == 4) {
        list->SortedInsert(threadInfo, threadInfo->currentBurst);
    } else {
        list->Append(threadInfo);
    }
    printf("Thread %d needs to burst %d times and is allowed to burst %d"
           " times per cycle\n",threadInfo->id = id, threadInfo->initialBursts,
           threadInfo->alottedBursts);
}



