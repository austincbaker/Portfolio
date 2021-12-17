package com.company;

import javax.sound.sampled.*;
import java.io.File;
import java.io.IOException;
import java.time.LocalTime;
import java.util.Arrays;

public class SoundRecorder implements Runnable {

    // the line from which audio data is captured
    private TargetDataLine line;
    private final String fileName;
    private final LocalTime end_time;

    public SoundRecorder(String fileName, LocalTime end_time){
        this.fileName = fileName;
        this.end_time = end_time;
    }
    /**
     * Defines an audio format
     */
    AudioFormat getAudioFormat() {
        float sampleRate = 44100;
        int sampleSizeInBits = 16;
        int channels = 2;
        boolean signed = true;
        boolean bigEndian = true;
        AudioFormat format = new AudioFormat(sampleRate, sampleSizeInBits,
                channels, signed, bigEndian);
        return format;
    }

    /**
     * Captures the sound and record into a WAV file
     */
    @Override
    public void run() {
        try {

            // path of the wav file
            File wavFile = new File("C:\\RecorderProgram\\Audio\\"+ fileName +".wav");

            // format of audio file
            AudioFileFormat.Type fileType = AudioFileFormat.Type.WAVE;

            AudioFormat format = getAudioFormat();

            DataLine.Info info = new DataLine.Info(TargetDataLine.class, format);

            //System.out.println(format.properties());
            // checks if system supports the data line
            if (!AudioSystem.isLineSupported(info)) {
                System.out.println(Arrays.toString(AudioSystem.getAudioFileTypes()));
                //System.out.println(line.getLineInfo());
                System.out.println("Line not supported");
                System.exit(0);
            }
            line = (TargetDataLine) AudioSystem.getLine(info);

            //System.out.println(format.properties());
            //System.out.println(line.getLineInfo());
            line.open(format);

            //System.out.println(format.properties());
            //System.out.println(line.getLineInfo());
            line.start();   // start capturing

            //System.out.println("Start capturing...");

            AudioInputStream ais = new AudioInputStream(line);

            //System.out.println("Start recording...");

            // start recording
            AudioSystem.write(ais, fileType, wavFile);

        } catch (LineUnavailableException | IOException ex) {
            ex.printStackTrace();
        }
    }

    /**
     * Closes the target data line to finish capturing and recording
     */
    void finish() {
        line.stop();
        line.close();
        System.out.println("Finished");
    }
}

