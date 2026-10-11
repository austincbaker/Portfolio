using System;
using System.IO;
using System.Drawing;
using System.Drawing.Imaging;
using System.Diagnostics;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;

//todo: Verify that endtime is being passed to the record class correctly

namespace recordingapp1
{
    class Program
    {

        //write return values to a text file and read from original java prog
        static void Main(string[] args)
        {

            string time = DateTime.Now.ToLocalTime().ToLongTimeString();
            Console.WriteLine(time);
            Console.WriteLine("Hello");
            string[] arguments = Environment.GetCommandLineArgs();
            Console.WriteLine("GetCommandLineArgs: {0}", string.Join(", ", arguments));
            string[] passedArgs = (args[0].Split(','));
            int year = int.Parse(passedArgs[0]);
            int month = int.Parse(passedArgs[1]);
            var day = int.Parse(passedArgs[2]);
            var hour = int.Parse(passedArgs[3]);
            var min = int.Parse(passedArgs[4]);
            var sec = int.Parse(passedArgs[5]);
            int[] retInt = new int[6];
            retInt[0] = year;
            retInt[1] = month;
            retInt[2] = day;
            retInt[3] = hour;
            retInt[4] = min;
            retInt[5] = sec;


            Rectangle rectangle = new Rectangle();
            rectangle.Height = int.Parse(passedArgs[6]);
            rectangle.Width = int.Parse(passedArgs[7]);

            Console.WriteLine(year);
            Console.WriteLine(month);
            Console.WriteLine(day);
            Console.WriteLine(hour);
            Console.WriteLine(min);
            Console.WriteLine(sec);
            Console.WriteLine(new DateTime(year, month, day, hour, min, sec));
            DateTime endTime = new DateTime(year, month, day, hour, min, sec);
            ScreenRecorder sr = new ScreenRecorder(rectangle, endTime);
            Thread t1 = new Thread(new ThreadStart(sr.RecordScreenshots));
            Thread t2 = new Thread(new ThreadStart(sr.RecordScreenshots));
            sr.RecordScreenshots();
            t1.Start();
            t2.Start();
            while (t2.IsAlive)
            {
                if (DateTime.Now.ToLocalTime() > endTime)
                {
              
                    break;
                }
            }
            t1.Interrupt();
            t2.Interrupt();
            Console.WriteLine("Done!");
        }
    }

    class ScreenRecorder
    {
        //Video variables:
        private Rectangle bounds;
        private string outputPath = "C:\\RecorderProgram\\Audio\\";
        private string tempPath = "C:\\RecorderProgram\\Screenshots\\";
        private DateTime endTime;
        private List<string> inputImageSequence = new List<string>();

        //File variables:
        private string videoName = "video.mp4";
        private string finalName = "FinalVideo.mp4";

        //Time variable:
        Stopwatch watch = new Stopwatch();

        public Rectangle Bounds { get => bounds; set => bounds = value; }
        public string OutputPath { get => outputPath; set => outputPath = value; }
        public string TempPath { get => tempPath; set => tempPath = value; }
        public DateTime EndTime { get => endTime; set => endTime = value; }
        public List<string> InputImageSequence { get => inputImageSequence; set => inputImageSequence = value; }
        public string VideoName { get => videoName; set => videoName = value; }
        public string FinalName { get => finalName; set => finalName = value; }
        public Stopwatch Watch { get => watch; set => watch = value; }


        //ScreenRecorder Object:
        public ScreenRecorder(Rectangle b, DateTime et)
        {
            Bounds = b;
            EndTime = et;

            //create the stopping time
        }

        //Record :
        public void RecordScreenshots()
        {
            var time = DateTime.Now.ToLocalTime();
            while (time < EndTime)
            {
                using (Bitmap bitmap = new Bitmap(Bounds.Width, Bounds.Height))
                {
                    using (Graphics g = Graphics.FromImage(bitmap))
                    {
                        //Add screen to bitmap:
                        g.CopyFromScreen(new Point(Bounds.Left, Bounds.Top), Point.Empty, Bounds.Size);
                    }
                    //Save screenshot:
                    string tstring = Watch.ElapsedMilliseconds.ToString();
                    string name = TempPath + "screenshot-" + Stopwatch.GetTimestamp() + ".jpeg";
                    bitmap.Save(name, ImageFormat.Jpeg);
                    InputImageSequence.Add(name);

                    //Dispose of bitmap:
                    bitmap.Dispose();
                    time = DateTime.Now;
                }
            }
        }
    }
}
