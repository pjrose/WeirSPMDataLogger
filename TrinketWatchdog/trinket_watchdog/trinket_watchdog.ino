 
static const int PI_OK_PULSE_TRAIN_PIN = 1;
static const int UPS_RESET_PIN = 4;
static const int PWR_ON_PIN = 0;
static const int DISABLE_CHECK_PIN = 3;
static const int BATT_VOLTS_AIN_PIN = 1; //MARKED AS PIN #2 ON THE BOARD, BUT MAPPED AS 'A1', HENCE '1'. measures battery voltage connected through a 10k/1k divider

static const int BATT_VOLTS_OK = 536; //ad counts, ~19v through divider or 1.727 v raw.
static const int BATT_VOLTS_OK_COUNT_PWR_ON_TRIGGER = 50;  //number of successive reads that batt_volts has to be above the BATT_VOLTS_OK level in order to power on the system, BATT_VOLTS_OK_COUNT_PWR_ON_TRIGGER * SYS_CHECK_INTERVAL = ms - nominally 50*100 = 5 seconds
static const int BATT_VOLTS_LOW = 508; //ad counts, ~18v through divider, or 1.636 v raw.
static const int BATT_VOLTS_LOW_COUNT_PWR_OFF_TRIGGER = 100; //number of successive reads that batt_volts has to be below the BATT_VOLTS_LOW level in order to power off the system, BATT_VOLTS_LOW_COUNT_PWR_OFF_TRIGGER * SYS_CHECK_INTERVAL = ms - nominally 100*100 = 10 seconds
static const int SYS_CHECK_INTERVAL = 100; //ms
static const int STARTUP_TIME = 30000; //ms
static const int UPS_RESET_HOLD_TIME = 3000; //ms
static const int UPS_INITIALIZATION_TIME = 6000; //ms
static const int SHUTDOWN_TIME = 150000; //ms, 1.5 minutes, pico default is 120 seconds of runtime after cable power loss
static const int NO_CHANGE_COUNT_PWR_OFF_TRIGGER = 2400; //ms, if battery ok and no change on pi pin for NO_CHANGE_COUNT_PWR_OFF_TRIGGER * SYS_CHECK_INTERVAL, then call reset_system()- nominally 100*2400 = 240 seconds (4 minutes)

//4 minutes was chosen becuase a power cycle reset initiated by this device should be the last resort to bring the system back to life.
//other system watchdogs already implemented at the time this solution was developed: 
//if the datacollection script can't read i2c sta_counter register on the UPS for 5 seconds, the script will quit and systemd will restart it.
//if the oil sensor returns no data for 15 seconds, a default message will be logged and the script will quit and systemd will restart it.
//if main thread does not receive any messages for 60 seconds (should received one per second from datacollection thread), then the script will quit and systemd will restart it, guards against exception in data collection thread
//if upload thread does not receive any data for 120 seconds, it will raise a queue empty exception, pass it to main, then the script will quit and systemd will restart it, guards against exception in main thread after receiving "new data"
//if systemd doesn't get a watchdog ping within 150 seconds, it will kill and restart the process. watchdog is pinged after every message received in main thread
//if the UPS doesn't get a watchdog ping within 180 seconds of starting the datacollection script, it will shutdown and reset the Pi, watchdog is pinged after new data is successfully processed in the main thread

static const int POWER_OFF_RESETS = 1; //number of times that the sketch will try power off in conjunction with UPS reset before falling back to only UPS reset with power on.

int no_change_count = 0;  //how many times in a row that the PI_OK_PULSE_TRAIN_PIN has not changed state
int pi_ok_pulse_train_level = 0;
int last_pi_ok_pulse_train_level = 0;
int batt_volts = 0;
int batt_volts_ok_count = 0;
int batt_volts_low_count = 0;
int reset_enabled = 0; //holds the state on DISABLE_CHECK_PIN, 0 means 'do not perform the reset' (the pin is physically jumpered to ground), 1 means 'resets are allowed/expected' (the pin has a pullup to 3.3V on the trinket board
int reset_attempt_count = 0; 
                    //if reset_attempt_count = 0, first attempt reset the system, usually after things were working but now they are not. Execute power off, wait 60 seconds, reset ups for 3 seconds, release ups reset and returns (calling loop will run apply power()then check_system())
                    //if reset_attempt_count >= POWER_OFF_RESETS, then the first (or second) reset cycle did not work. The sketch will try holding the reset ups pin low for 3 seconds, then release it, then wait 30 seconds. Sometimes this works if the pi is powered and responsive, but the UPS is locked up.

// the setup routine runs once when you press reset:
void setup()
{  
  pinMode(PI_OK_PULSE_TRAIN_PIN, INPUT);
  digitalWrite(PWR_ON_PIN, LOW); //must be called before pinMode(...)
  pinMode(PWR_ON_PIN, OUTPUT);
  digitalWrite(UPS_RESET_PIN, HIGH); //must be called before pinMode(...) so that the pin is not set low by default, which would reset the UPS
  pinMode(UPS_RESET_PIN, OUTPUT);
}


 
// the loop routine runs over and over again forever:
void loop()
{
  apply_power();
  
  check_system();

  if(no_change_count >= NO_CHANGE_COUNT_PWR_OFF_TRIGGER) //must have exited due to no change on the PI_OK_PULSE_TRAIN_PIN digital input
  {
    reset_system(); 
  }
  else //must have exited due to battery voltage low
  {
    digitalWrite(PWR_ON_PIN, LOW);
    delay(SHUTDOWN_TIME); 
  }
  
  no_change_count = 0;
  batt_volts_low_count = 0;
}

void apply_power()
{ 
  bool battery_ok = false; //local flag used as a trap in this function's while loop
  
  batt_volts_ok_count = 0; 
  batt_volts_low_count = 0;
  
  do
  {
     batt_volts = analogRead(BATT_VOLTS_AIN_PIN);

     if(batt_volts >= BATT_VOLTS_OK)
     {
        batt_volts_ok_count++; //increment the 'good' count 
        batt_volts_low_count = 0; //reset the 'bad' count 

                
        if(batt_volts_ok_count >= BATT_VOLTS_OK_COUNT_PWR_ON_TRIGGER)
        {
          digitalWrite(PWR_ON_PIN, HIGH);
          delay(STARTUP_TIME);
          
          battery_ok = true; //will cause this do-while loop to exit
        }
     }
     else //battery level is low, turn off power if it stays low for too long
     {
        batt_volts_low_count++; //increment the 'bad' count 
        batt_volts_ok_count = 0; //reset the 'good' count
        
        if(batt_volts_low_count >= BATT_VOLTS_LOW_COUNT_PWR_OFF_TRIGGER)
        {
          batt_volts_low_count = 0; //guard against rollover.
          digitalWrite(PWR_ON_PIN, LOW);
        }    
        delay(SYS_CHECK_INTERVAL);
     }
       
  } while(battery_ok == false);
   
  return; //caller (loop()) will call check_system() next
}

void check_system()
{
  do
  {
    reset_enabled = digitalRead(DISABLE_CHECK_PIN); //default state is 1, 0 means a jumper is installed which will prevent watchdog timeouts.
    pi_ok_pulse_train_level = digitalRead(PI_OK_PULSE_TRAIN_PIN);
    batt_volts = analogRead(BATT_VOLTS_AIN_PIN);
    
    if(batt_volts < BATT_VOLTS_LOW)
    {
       batt_volts_low_count++; 
    }
    else
    {
      batt_volts_low_count = 0;
    }
    
    if(pi_ok_pulse_train_level == last_pi_ok_pulse_train_level) 
    {
      no_change_count++;
    }
    else
    {
      no_change_count = 0;
    }

    if(batt_volts_low_count == 0 && no_change_count == 0)
    {
     reset_attempt_count = 0; //the last reset cycle must have been successful, or the system just successfully booted and all systems are operating normally, this will cause the system to do a power off reset next time reset() is called
    }
    
    last_pi_ok_pulse_train_level = pi_ok_pulse_train_level;
    
    delay(SYS_CHECK_INTERVAL);
  } while(reset_enabled == 0 || (batt_volts_low_count < BATT_VOLTS_LOW_COUNT_PWR_OFF_TRIGGER && no_change_count < NO_CHANGE_COUNT_PWR_OFF_TRIGGER)); //keep doing this as long as the battery volts are OK and the pi is signaling 'OK'. if reset_enabled == 0, then the watchdog bypass jumper is installed, and it should never exit this while loop

  return; //caller (loop()) will call reset_system() next
}

void reset_system()
{
  if(reset_attempt_count == 0)
  {
     digitalWrite(PWR_ON_PIN, LOW);
     delay(SHUTDOWN_TIME); //allow time for complete power off (if UPS is working)
     digitalWrite(UPS_RESET_PIN, LOW);
     delay(UPS_RESET_HOLD_TIME); 
     digitalWrite(UPS_RESET_PIN, HIGH);
     delay(UPS_INITIALIZATION_TIME); 
     reset_attempt_count++;
  }
  else if(reset_attempt_count >= POWER_OFF_RESETS)
  {
     digitalWrite(UPS_RESET_PIN, LOW);
     delay(UPS_RESET_HOLD_TIME); 
     digitalWrite(UPS_RESET_PIN, HIGH);
     delay(UPS_INITIALIZATION_TIME); 
     reset_attempt_count = 0; //this will force a power off reset on next call
  }
  
  return; //caller (loop()) will call apply_power() next, if we executed the case where reset_attempt_count >= POWER_OFF_RESETS, the power is already (still) on, so apply_power() will just check the battery voltage and move on if it's ok, or turn it off if not ok.
}

    
