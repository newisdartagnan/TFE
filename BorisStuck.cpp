#include <stdio.h>
#include <opencv2/opencv.hpp>
#include <fstream>
#include <iostream>
#include <wiringPi.h>
#include <opencv2/core/ocl.hpp>
#include "tensorflow/lite/interpreter.h"
#include "tensorflow/lite/kernels/register.h"
#include "tensorflow/lite/string_util.h"
#include "tensorflow/lite/model.h"
#include <chrono>
#include <unistd.h>
#include <thread>
#include <httplib.h>
#include <nadjieb/mjpeg_streamer.hpp>
// Définir les numéros des broches GPIO du Raspberry Pi 4 pour le capteur ultrasonique
#define TRIG 21 // Broche GPIO 5 en numérotation WiringPi
#define ECHO 22 // Broche GPIO 6 en numérotation WiringPi
#define SOUND_SPEED 34000 // Définir la vitesse du son en cm/s à température ambiante

using namespace cv;
using namespace std;
using MJPEGStreamer = nadjieb::MJPEGStreamer;

const size_t width = 640;
const size_t height = 480;

std::vector<std::string> Labels;
std::unique_ptr<tflite::Interpreter> interpreter;

// Définir une constante pour le nombre de mesures à comparer
const int N = 25; // Nombre de mesures à comparer
const int T = 6000; // Intervalle de temps (en ms
//Définir un tableau pour stocker les distances
double distances[N];
int ind = 0;
// Définir une variable pour mémoriser le temps précédent
long previousTime = 0;

void setup() {
    wiringPiSetup(); // Configurer les broches GPIO en mode WiringPi
    pinMode(TRIG, OUTPUT); // Configurer la broche TRIG en sortie
    pinMode(ECHO, INPUT); // Configurer la broche ECHO en entrée
    digitalWrite(TRIG, LOW); // Mettre la broche TRIG à l'état bas
    delay(2000); // Attendre 2 secondes pour que le capteur se stabilise
}

void send_message(const std::string& action) {
        httplib::Client cli("http://0.0.0.0:8000");
    auto res = cli.Get(("/run/?action=" + action).c_str());

    if (res && res->status == 200) {
        std::cout << action + ": Request successful." << std::endl;
    } else {
        std::cerr << action + ": Error: Request failed" << std::endl;
    }
}

int getDistance() {
    // Trigger the sensor
    long startTime, endTime;
    double distance;

    // Envoyer une impulsion de 10 microsecondes
    digitalWrite(TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG, LOW);

    while(digitalRead(ECHO) == LOW); // Attendre que ECHO passe à l'état haut
    startTime = micros(); // Temps de départ
    while(digitalRead(ECHO) == HIGH); // Attendre que ECHO passe à l'état bas
    endTime = micros(); // Temps d'arrivée
    // Calculer la durée et la distance
    distance = (endTime - startTime) * SOUND_SPEED / 2000000.0;
    return distance;
}

// Fonction pour calculer la moyenne d'un tableau de nombres
double average(double arr[], int size) {
    // Définir une variable pour stocker la somme
    double sum = 0;
    // Définir une variable pour compter le nombre de distances logiques
    int count = 0;
    // Parcourir le tableau
    for (int i = 0; i < size - 1; i++) {
        // Calculer la différence absolue entre deux mesures consécutives
        double diff = abs(arr[i] - arr[i + 1]);
        // Si la différence est inférieure à 3 cm, c'est une distance logique
        if (diff < 3) {
            // Ajouter la distance à la somme
            sum += arr[i];
            // Incrémenter le compteur
            count++;
        }
    }
    // Retourner la moyenne
    return sum / count;
}

// Fonction pour vérifier si le robot est bloqué
bool isStuck(double distances[]) {
    // Calculer la moyenne des 25 mesures
    double mean = average(distances, N);
    // Obtenir la dernière mesure
    double last = distances[N - 1];
    // Calculer la différence absolue entre la moyenne et la dernière mesure
    double diff = abs(mean - last);
    // Retourner le résultat booléen
    return diff < 1;
}

static bool getFileContent(std::string fileName) {
    // Open the File
    std::ifstream in(fileName.c_str());
    // Check if the object is valid
    if (!in.is_open()) return false;

    std::string str;
    // Read the next line from File until it reaches the end.
    while (std::getline(in, str)) {
        // Line contains a string of length > 0, then save it in the vector
        if (str.size() > 0) Labels.push_back(str);
    }
    // Close The File
    in.close();
    return true;
}

void detect_from_camera() {
    Mat frame;
    VideoCapture cap(CAP_V4L2); // Use the default camera (you can change the ind if you have multiple cameras)
    cap.set(CAP_PROP_FRAME_WIDTH, width);
    cap.set(CAP_PROP_FRAME_HEIGHT, height);

    if (!cap.isOpened()) {
        cerr << "ERROR: Unable to open the camera" << endl;
        return;
    }

// MJPEG Streamer
    std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, 90};
    MJPEGStreamer streamer;
    streamer.start(8080);


    int delay = 1000 / 30; // Delay in milliseconds to achieve 30 FPS

    cout << "Start grabbing, press ESC to terminate" << endl;
    int frame_count = 0;
    double total_fps = 0.0;

    //les variables de comptes
    int shortDistance = 0;

    while (streamer.isRunning()) {
        cap >> frame;
        if (frame.empty()) {
            cerr << "ERROR: Unable to grab from the camera" << endl;
            break;
        }

        // Copy image to input as input tensor
        Mat input_image;
        cv::resize(frame, input_image, Size(300, 300));
        memcpy(interpreter->typed_input_tensor<uchar>(0), input_image.data, input_image.total() * input_image.elemSize());

        interpreter->SetAllowFp16PrecisionForFp32(true);
        interpreter->SetNumThreads(4); // Quad core

        // Calculate object distance using the HC-SR04 sensor
        int distance = getDistance();

        auto start_time = chrono::high_resolution_clock::now();
        interpreter->Invoke(); // Run your model
        auto end_time = chrono::high_resolution_clock::now();
        double elapsed_ms = chrono::duration<double, milli>(end_time - start_time).count();

        const float *detection_locations = interpreter->tensor(interpreter->outputs()[0])->data.f;
        const float *detection_classes = interpreter->tensor(interpreter->outputs()[1])->data.f;
        const float *detection_scores = interpreter->tensor(interpreter->outputs()[2])->data.f;
        const int num_detections = *interpreter->tensor(interpreter->outputs()[3])->data.f;

        const float confidence_threshold = 0.5;
        for (int i = 0; i < num_detections; i++) {
            if (detection_scores[i] > confidence_threshold) {
                int det_ind = (int)detection_classes[i] + 1;
                float y1 = detection_locations[4 * i] * height;
                float x1 = detection_locations[4 * i + 1] * width;
                float y2 = detection_locations[4 * i + 2] * height;
                float x2 = detection_locations[4 * i + 3] * width;

                Rect rec((int)x1, (int)y1, (int)(x2 - x1), (int)(y2 - y1));
                rectangle(frame, rec, Scalar(0, 0, 255), 1, 8, 0);
                putText(frame, format("%s", Labels[det_ind].c_str()), Point(x1, y1 - 5), FONT_HERSHEY_SIMPLEX, 0.5, Scalar(0, 0, 255), 1, 8, 0);

                // Calculate object distance
                float object_width = x2 - x1;
                if (object_width > (0.85 * width)) {
                                        // Object is very close
                    putText(frame, "STOP!!! Object is very close!", Point(10, 40), FONT_HERSHEY_SIMPLEX, 0.6, Scalar(0, 0, 255), 2, 8, 0);

                } else if (object_width > (0.7 * width)) {
                    // Object is getting closer
                    putText(frame, "WARNING!! Object is getting closer.", Point(10, 70), FONT_HERSHEY_SIMPLEX, 0.6, Scalar(0, 0, 255), 2, 8, 0);
                }
            }
        }

        // Affichage de la distance au coin en bas à droite
        std::string distance_message = "Distance: " + std::to_string(distance) + " cm";
        std::cout << distance_message << std::endl;
        putText(frame, distance_message, Point(frame.cols - 200, frame.rows - 20), FONT_HERSHEY_SIMPLEX, 0.6, Scalar(0, 255, 0), 2, 8, 0);

        //behaviour
        if (distance <= 39) {
            shortDistance++;
            if (shortDistance >= 7){
                std::cout << "STOP!!! Object is very close" << std::endl;
                std::thread send_thread(send_message, "stop");
                send_thread.detach(); // Detach the thread and let it run independently
                shortDistance = 0;
                sleep(8);
            }
        } else shortDistance = 0;
        distances[ind] = distance;
        ind = (ind + 1) % N;
        // Obtenir le temps actuel en ms
        long currentTime = millis();
        if (currentTime - previousTime > T) {
            // Vérifier si le robot est bloqué
            if (isStuck(distances)) {
                // Afficher un message d'alerte
                cout << "Le robot est peut-être bloqué !" << endl;
                std::cout << currentTime - previousTime << endl;
                // Envoyer un message à un autre thread
                thread send_thread(send_message, "checkStuck");
                send_thread.detach();
            }
            previousTime = currentTime;
        }

        // Update the previous distance
        //previousDistance = distance;

        // Calculate FPS
        double fps = 1000.0 / elapsed_ms;
        total_fps += fps;
        frame_count++;

        putText(frame, "FPS: " + to_string(fps), Point(10, 20), FONT_HERSHEY_SIMPLEX, 0.6, Scalar(0, 0, 255), 2, 8, 0);

        //MJPEG streamer instead of imshow
        std::vector<uchar> buff_bgr;
        cv::imencode(".jpg", frame, buff_bgr, params);
        streamer.publish("/bgr", std::string(buff_bgr.begin(), buff_bgr.end()));

        char esc = waitKey(delay); // Use the specified delay
        if (esc == 27) break;
    }

    if (frame_count > 0) {
        double average_fps = total_fps / frame_count;
        cout << "Average FPS: " << average_fps << endl;
    }

    streamer.stop();

        cout << "Closing the camera" << endl;
    destroyAllWindows();

}

void camera_thread() {
    // Start the camera capture
    detect_from_camera();
}

void ultrasonic_thread() {
    while (true) {
        getDistance();

        // Attendre un certain temps avant de mesurer à nouveau
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

int main(int argc, char **argv) {
    // Initialisation ultrasonic
    setup();
    // Load model
    std::unique_ptr<tflite::FlatBufferModel> model = tflite::FlatBufferModel::BuildFromFile("detect.tflite");

    // Build the interpreter
    tflite::ops::builtin::BuiltinOpResolver resolver;
    tflite::InterpreterBuilder(*model.get(), resolver)(&interpreter);

    interpreter->AllocateTensors();

    // Get the names
    bool result = getFileContent("COCO_labels.txt");
    if (!result) {
        cout << "Loading labels failed";
        return -1;
    }
    // Démarrer la fonction detect_from_camera() dans un thread séparé
    std::thread camera_capture_thread(camera_thread);

    // Démarrer la fonction getDistance() dans un thread séparé
    std::thread ultrasonic_thread_obj(ultrasonic_thread);

    // Attendre la fin du thread de capture de la caméra
    camera_capture_thread.join();

    // Attendre la fin du thread ultrasonic
    ultrasonic_thread_obj.join();

    return 0;
}
