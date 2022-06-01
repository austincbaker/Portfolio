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