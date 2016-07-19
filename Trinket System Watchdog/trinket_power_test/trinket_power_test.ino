 
const int PI_OK_PULSE_TRAIN_PIN = 1;
const int UPS_RESET_PIN = 4;
const int PWR_ON_PIN = 0;
const int DISABLE_CHECK_PIN = 3;
const int BATT_VOLTS_AIN_PIN = 1; //PHYSICALLY PIN #2, connected through a 10k/1k divider

const int BATT_VOLTS_OK = 536; //ad counts, ~19v through divider or 1.727 v raw.
const int BATT_VOLTS_LOW = 508; //ad counts, ~18v through divider, or 1.636 v raw.
const int BATT_VOLTS_LOW_COUNT_PWR_OFF_TRIGGER = 100; //number of successive reads that batt_volts has to be below the BATT_LOW level in order to power off the system, BATT_VOLTS_LOW_COUNT_PWR_OFF_TRIGGER * SYS_CHECK_INTERVAL = ms - nominally 100*100 = 10 seconds
const int SYS_CHECK_INTERVAL = 100; //ms
const int STARTUP_TIME = 30000; //ms
const int UPS_RESET_HOLD_TIME = 3000; //ms
const int UPS_INITIALIZATION_TIME = 6000; //ms
const int SHUTDOWN_TIME = 60000; //ms
const int NO_CHANGE_COUNT_PWR_OFF_TRIGGER = 600; //ms, if battery ok and no change on pi pin for NO_CHANGE_COUNT_PWR_OFF_TRIGGER * SYS_CHECK_INTERVAL, then call reset_system()- nominally 100*600 = 60 seconds
const int POWER_OFF_RESETS = 1; //number of times that the sketch will try power off in conjunction with UPS reset before falling back to only UPS reset with power on.


int no_change_count = 0;  //how many times in a row that the PI_OK_PULSE_TRAIN_PIN has not changed state
int pi_ok_pulse_train_level = 0;
int last_pi_ok_pulse_train_level = 0;
int batt_volts = 0;
int batt_volts_low_count = 0;
int reset_enabled = 0; //holds the state on DISABLE_CHECK_PIN, 0 means 'do not perform the reset' (the pin is physically jumpered to ground), 1 means 'resets are allowed/expected' (the pin has a pullup to 3.3V on the trinket board
int reset_attempt_count = 0; 
                    //if reset_attempt_count = 0, first attempt reset the system, usually after things were working but now they are not. Execute power off, wait 60 seconds, reset ups for 3 seconds, release ups reset and returns (calling loop will run apply power()then check_system())
                    //if reset_attempt_count >= POWER_OFF_RESETS, then the first (or second) reset cycle did not work. The sketch will try holding the reset ups pin low for 3 seconds, then release it, then wait 30 seconds. Sometimes this works if the pi is powered and responsive, but the UPS is locked up.

// the setup routine runs once when you press reset:
void setup()
{  
  pinMode(PI_OK_PULSE_TRAIN_PIN, INPUT);
  pinMode(PWR_ON_PIN, OUTPUT);
  digitalWrite(UPS_RESET_PIN, HIGH); //must be called before pinMode(...) so that the pin is not set low by default, which would reset the UPS
  pinMode(UPS_RESET_PIN, OUTPUT);
}


 
// the loop routine runs over and over again forever:
void loop()
{

     batt_volts = analogRead(BATT_VOLTS_AIN_PIN);

     if(batt_volts >= BATT_VOLTS_OK)
     {
        batt_volts_low_count = 0;
        digitalWrite(PWR_ON_PIN, HIGH);
     }
     else //battery level is low, turn off power if it stays low for too long
     {
        batt_volts_low_count++; //increment the count 

        if(batt_volts_low_count >= BATT_VOLTS_LOW_COUNT_PWR_OFF_TRIGGER)
        {
          batt_volts_low_count = 0; //reset so we don't delay(shutdown_time) again
          digitalWrite(PWR_ON_PIN, LOW);
        }    
     }

     delay(100);   

   
}






    
