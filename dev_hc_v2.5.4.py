#! /usr/bin/python
### --Version 2.5
### NETSCOUT IS and PM Device Health check script prepared by Syed Rehman(last updated 12/01/15)
### Included date,hwclock,uptime,load_average and serial number on IS data (01/20/16)
### Included Multithreading module to trigger parallel SSH commands to PMs and IS boxes (02/04/16)
### Included several other metrics for IS and PM. For complete List see IS_col and PM_col (02/16/16)
### Added IS_error_summary and PM_error_summary output and email body  (02/20/16)
### Added following Infinistreams metrics:- 'IS_Processes' ,'Disk_available(/metadata)' (03/17/16)
### Added following PM metrics:-  'upitme', 'OS version', 'Disk_available(/)','PM Postgres threads','PM Webservice threads','PM ngenius processes' (03/17/16)           
### Added Infinistream Processes check and PM Database, Webservice and Diskavailable checks on error summaries (03/18/16)
### Corrected bug around Disk Size check (03/18/16)
### Fixed the missing data around  Peak PM process memories column (03/18/16) 
### Inserted space between table drop entries to make them better visible (03/19/16)    
### Script gets hung while generating nshwmon script on some of 8995Ds . Script now has been modified to use nshwmon logs instead of generating it. 
### Table drops in IS have been modified to show only the more recent drops i.e. from yesterday to current. (03/25/16)
### As a result script is now much faster than before.(03/23/16)
### Core File metric in IS has been modified to show core files generated within last 48 hrs.(03/25/16)   
### included number of rows against each table in error summary. (03/25/16)
### Script has been modified to support IPv6 PMs and IS  (03/27/16)
### Few PM HW status metrics added from 'omreport chassis command'(03/27/16)
### Fan Status',	'Memory Status','Power Status','Temp Status','Voltage Status','Batteries Status'
### 'Failed HDD' has be on PM report (03/27/16)
### Fixed the bug around PM memory showing mulitple values, causing error summary to miss the errors (04/14/16)
### Change Disk_available description to Disk_Size on IS (04/14/16)
### Added IS interfaces Link status report in html using hourly_vital_stats table in Local PMs(05/12/16)
### Added DB connection status in PM report and checking it on error function if its greater than 90(05/10/16)
### Added version information on email body (suggested by Brandon) (05/10/16)
### Changed the column name:Disk_available(/opt) to Disk_Use(/opt) on PM reports. (05/12/16)
### PM peak memory utilizion to report the latest data instead of yesterday(05/12/16)
### Added /xdr Disk usage in IS report (05/15/16)
### Added Partition check on IS '/', '/metadata' and '/xdr partitions' (05/15/16)
### Full Reports and error summary data are now sorted based on IPs (05/15/16)
### Date information has been added on error summaries (05/15/16)
### Fixed bug in v1.5, reported around list assignment when number of PMs are lesser than cpu threads. (05/16/16)
### Inluded IPv6 support for link function(05/17/16)
### Included IS count in Link report (05/19/16)
### Included Sip_db_sessions in link report (05/19/16)
### Included Sip_db_sessions in link report (05/19/16)
### Added ssh timeout function to report IS or PM (that are pingable) but couldnt ssh, timeout value is 60s.(06/12/16)
### Added NTP not running error check in error report (06/30/16)
### Added "Missing" HDD detection (suggested by David, Ang)(07/15/16)
### Added PM Restart detection in full report and error check  (07/15/16)
### Added Peak ASI rows and ASI logging time column for PMs (08/03/16)
### Added IS interface type in link report (08 /08/16)
### Added CDM count and changed NTP ouput separator(Taral)(08 /08/16)
### Added XDR Size, Oldest XDR date and Packet Store Size columns in IS csv report (08 /08/16)
### Added Peak PPS Time in IS_link html Report(09/26/16)
### Added nsprobe memory in IS_link html Report(10/20/16)
### IS_link Report should not show IS that are not IS file(10/20/16)
### Included Infinistream timeout during past 24 hour in PM Report(10/25/16)
### Included PM Blackout During Today(10/25/16)
### Included PM config backup check (10/26/16)
### Included Peak Active streams metric in IS_link Report (10/26/16)
### Fixed  the broken IS_link Report for 5.5.2 environment  (10/26/16)
### Added GTPv2 correlation stats (12/19/16)
### Aggregated several metrics and added Health check summary on email body
### Added S1 nas deciphering rate for s1 interfaces (suggested by Rafi and Surya)
### Merged PM and IS error files into one file
### Changed IS_link_table_status file name to IS_Interface_Stats.html
### Added SCSI error checks on PM devices (suggested by Patricia)
### Added Interface types in IS_Healthcheck data (suggested by Norm)
### Added Voice monitotring, ASI mode in IS_Healthcheck 
### Deprecated error checks on 200 days for IS as the issue has been resolved in 5.5.
### Added localconsole inaccessible and nshwmon log error checks for IS.

##########################################################################################################################################
 
import os
import sys
import subprocess
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEBase import MIMEBase
from email import Encoders
import getopt
import csv
import re
from threading import Thread
from time import ctime
import time
import datetime
import signal
import copy


SCRIPT_DIR='/opt/vzw_scripts/Health-checks/v2.5' ### Directory for script *****Make sure full dir path has user login permissions
DIR = SCRIPT_DIR+'/Results'  ### Directory for Healthcheck outputs



### Create if Results dir  not exists
if not os.path.exists(DIR):
  try:
     os.makedirs(DIR)
  except IOError:
     sys.exit( 'Unable to acess ' + SCRIPT_DIR )

Version ='2.5'
From = "nGenius@netscout.com"
To = ['syed.rehman@netscout.com','syed.rehman@verizonwireless.com']
Deployment='South'
SMTP_IP='10.194.80.114' ### SMTP IP for sending emails
S1MME           = True    ### True if deployment is monitoring s1mme interfaces (only for Wireless Service Provider EPC monitoring) else False.
GTPv2_DATA_Corr = True    ### True if monitoring data plane (for e.g. S1U/S5U) with control plane (S11/S5).
Voice_IS        = True    ### True if deployment has voice monitoring enabled on any IS else False.
Ping_Disable    = False   ### True if Network has ICMP blocked. The script wont check Ping status if set to True, otherwise keep it False 
Config_Backup   = '/opt/NetScout/rtm/database/config-backup'   ### Default Config backup dir, please change if it is different.
Login           = 'netscout'  ###USER LOGIN ***Make sure SSH trusts are already created with this login


IS_t=0
IS_u=0
PM_t=0
PM_u=0
PM_l=[]
IS_l=[]
PM_s=[]
IS_s=[]
is_output={}
pm_output={}

#def eprint(*args, **kwargs):
    #print(*args, file=sys.stderr, **kwargs)


def main(argv):
   
   global subject
   global output 
   global is_output
   global pm_output
   global Deployment
   global SMTP_IP
   global Voice_IS
   
   is_list_output=[]
   pm_list_output=[]
   date_today=time.strftime("%Y-%m-%d", time.localtime())
   try:
      opts, args = getopt.getopt(argv,"f:i:l:s:")
   except getopt.GetoptError:
      print './dev_hc.v2.5.py -f <PMs IP file> -i < IS IP file> -l <Link_Status: Yes or No> -s <email subject>'
      sys.exit()
   for opt, arg in opts:
      if opt == '-f':
         pmip = arg
      elif opt== '-i':
         is_ip = arg
      elif opt== '-l':
         ln_status = arg
      elif opt== '-s':
         subject = arg 
   #### Check the no. of CPUs in the box
   cpus=int(os.popen('grep processor /proc/cpuinfo|wc -l').read().rstrip())
   if cpus >= 8 and cpus-5 >= cpus/2:
      cpus=cpus-5
   else:
      cpus=cpus-2
   print "cpus_thread :%s " %cpus    
   chunks = lambda L,n: [L[i:i+n] for i in range (0, len(L),n)]  
   #DIR=os.path.dirname(os.path.realpath(__file__)) ## to get the current directory where the script exist
   
   #### Gathering and writing PM data ##
   PM_col= ['Hostname', 'IP','PM_Type', 'Uptime','Total-CPU','Total-Mem' ,'Serial_number', 'Linux Kernel version', 'OS version', 'Software version', 'NTP IP','NTP_strartum Status','NTP Delay', 'HDD','Failed HDD',
   'Fan Status', 'Memory Status','Power Status','Temp Status','Voltage Status','Batteries Status', 'Peak CPU utilization','DELL OMSA version', 'iDrac version', ' iDrac IP', 'iDrac link connected', 'Disk_Size(/opt)','Disk_Use(/opt)','Disk_Use(/)',
   'Peak content_memory', 'Peak asiwarehouse_memory', 'Peak asiservicewarehouse_memory', 'Peak webxpresentmemory', 'Peak uccontentmemory',
   'Peak CDM loggermemory', 'Peak CDM flowloggermemory', 'Peak CDM fdsindexingmemory', 'Peak asi2xloggermemory', 'Peak analyticsmemory', 
   'Peak CDM whmemory', 'Peak webxreportgenmemory', 'Peak flowrollupmemory','Peak nssituationmemory','Peak CDM Rows/Flows','Peak ASI Rows','Peak ASI Logging Time (ms)','PM Postgres threads','PM Webservice threads','Number of DB Connections','Process Restart(Today)', 'Process Restart(Yesterday)', 'PM ngenius processes',
   'IS Timeout (During Past 24 hr)','PM Blackout (During Today)','Config_Backup Last Date','SCSI_err','Paservic Restart']
   pm = open( pmip , "r")
   pm_input_list= [i.rstrip() for i in pm]
   if len(pm_input_list) < cpus:
      pm_ip_list=chunks(pm_input_list,1)
   else:
      n=int(round((len(pm_input_list))/float(cpus)))
      pm_ip_list=chunks(pm_input_list,n)
   pm_thread_list=[]
   for i in range(len(pm_ip_list)):
     pm_Th=Thread(target = PM_thread, args=(pm_ip_list[i],))
     pm_Th.start()
     pm_thread_list.append(pm_Th)
   for t in pm_thread_list:
     t.join()
   #### sorting PM by hostname
   PM_OUT={}
   for l in pm_output.values():
     PM_OUT[l[0]]=l 
     
   #### pm_output post processing
   pm_output_post_processing(pm_output,PM_col)
   
   pm_out= open(DIR+"/%s_PM_Healthcheck.csv"%(Deployment),"wb") 
   c_pm = csv.writer(pm_out)
   c_pm.writerow(PM_col[:-1])
   for i in sorted(PM_OUT):
      c_pm.writerow(PM_OUT[i][:-1])
      pm_list_output.append(PM_OUT[i])
   pm_out.close()
   #### Initializing IS IPs in a List ###
   is1 = open( is_ip , "r")
   d=[i.rstrip() for i in is1]
   
   #### Probe's_Interfaces_link_summary##########################3
   link_data={}
   if ln_status == 'Yes' or ln_status =='yes':
       link_thread_list=[]
       
       for i in pm_ip_list:
             print"GP: Calling PM link thread :" 
             pm_link_Th=Thread(target = PM_link_thread, args=(i,link_data,d))
             pm_link_Th.start()
             link_thread_list.append(pm_link_Th)
       for t in link_thread_list:
          t.join()   
   
   ### Gathering and writing IS data ###
   IS_col= ['Hostname', 'IP', 'Date', 'HW_Clock', ' IPMI IP',  'Model', 'Version','Asi_mode', 'Serial Number','Linux kernel Version', 'CPU', 'Memory', 
   'Uptime', 'Load_Average','ESUs', 'HDD', 'Failed HDD', 'Failed HDD Desc','Failing HDD','Foreign HDD', 'FAN Status', 'POWER Status', 'Temperature Status', 'Voltage Status' ,
   'NTP IP','NTP_Strartum Status','NTP Delay(ms)', 'Core_File (Last 48 hrs)','Duplex_Mode', 'Disk_Use(/)','Disk_Use(/metadata)','Disk_Use(/xdr)',
   'XDR Size','Oldest XDR Date','Packet Store Size(GB)','PM Server','Voice Monitoring','Nsprobe Mem','Free_Mem', 'Table_Size_Allocation(ifn-size-ctrl-data)','nsprobe uptime',
   'IS_Processes','Table_Drops (Yesterday to Current)','Packet Data Retention','Error in /var/log/messages','Dengine gt than 8 hr','Interface_Type','Sip_db','GTPv2_corr','Vifn_mode','TCM Conn shortages']
   
   
   if len(d) < cpus:
      is_ip_list=chunks(d,1)
   else:
      n=int(round((len(d))/float(cpus)))
      is_ip_list=chunks(d,n)
   is_thread_list=[]
   for i in range(len(is_ip_list)):
       is_Th=Thread( target= IS_thread, args=(is_ip_list[i],link_data)) 
       is_Th.start()
       is_thread_list.append(is_Th)
   for t in is_thread_list:
       t.join()
   ####S1MME NAS_DECIPHERING#####
   if S1MME:
     IS_col.append('NAS_Deciphering rate %')
     s1_nas_deciphering(is_output,IS_col)
   
   ### is_output post processing
   is_output_post_processing(is_output,IS_col)
   
   is_out= open(DIR+"/%s_IS_Healthcheck.csv"%(Deployment), "wb") 
   c_is = csv.writer(is_out)
   c_is.writerow( IS_col[:-3])
   ###To Sort by Hostname
   is_hosts={}
   is_ip=[] ### output Lists sorted infinistreams hosts based on IP
   for k in is_output.values():
     is_hosts.update({k[0]:k})
   for l in sorted(is_hosts):
     is_ip.append(is_hosts[l][1])
       
   csv_is_output= IS_csv_data_processing(is_output,IS_col)
   
   for i in is_ip:
      c_is.writerow(csv_is_output[i][:-3])### Not writing Interface types/SIP_DB/gtpcorr/s1mme values on csv file  
      is_list_output.append(is_output[i])    
   is_out.close()
   
   ### IS error summary ##
   IS_err={'NTP Error':['16',IS_col.index('NTP_Strartum Status')], 'HDD Failed':['^[1-9]',IS_col.index('Failed HDD')], 
   'HDD Failing':['^[1-9]',IS_col.index('Failing HDD')],'HDD Foreign':['^[1-9]',IS_col.index('Foreign HDD')],
   'Power Failure':['DEGRADED',IS_col.index('POWER Status')],
   'Temp Failure':['DEGRADED',IS_col.index('Temperature Status')] ,'Voltage Failure':['DEGRADED',IS_col.index('Voltage Status')],'Fan Failure':['DEGRADED',IS_col.index('FAN Status')],
   'Disk Size(/metadata) >90%':['^9[1-9]|^100',IS_col.index('Disk_Use(/metadata)')],'Disk Size(/xdr) >90%':['^9[1-9]|^100',IS_col.index('Disk_Use(/xdr)')],'Half_Duplex':['Half',IS_col.index('Duplex_Mode')] ,'Disk Size(/) >90%':['^9[1-9]|^100',IS_col.index('Disk_Use(/)')],
   'Core File(s) -- last 48 hrs':['^[1-9]',IS_col.index('Core_File (Last 48 hrs)')],'Table Drops -- yesterday to current':['^(?!\s*$).+',IS_col.index('Table_Drops (Yesterday to Current)')],
   'IS Process(es) Not Running':['^(?!.*procmana)|^(?!.*tfaengin)|^(?!.*cleanupe)|^(?!.*nsprobe)|^(?!.*paservic)',IS_col.index('IS_Processes')],
   'Partition Missing (/metadata)':['^\s*$',IS_col.index('Disk_Use(/metadata)')],'Partition Missing (/xdr)':['^\s*$',IS_col.index('Disk_Use(/xdr)')], 'NTP Not Running':['^\s*$',IS_col.index('NTP_Strartum Status')],
   'NSHWMON log not generating(/opt/platform/nshwmon/log/nshwmon-logfiles)':['NA',IS_col.index('POWER Status')],'Localconsole Inaccessible':['NA',IS_col.index('Version')],
   'Error in /var/log/messages':['^(?!\s*$).*',IS_col.index('Error in /var/log/messages')],
   'Dengine Running > 8 hr':['^(?!\s*$).*',IS_col.index('Dengine gt than 8 hr')],
   'Tcm connection shortages': ['if_\d:[1-9]',IS_col.index('TCM Conn shortages')],
   'nsprobe uptime > 100 days': ['1[0-9][1-9] days',IS_col.index('nsprobe uptime')]}
   
   ##,'Uptime > 200 days':['up [2-9][0-9][0-9]',IS_col.index('Uptime')]--Deprecated inv2.4
   IS_err_summ=get_error_summary(IS_err, is_list_output) 
   print " IS error summary completed"
 
   ### PM error summary ###
   #mem =[ i for i in PM_col  if re.search('memory', i)] ## not working in python 2.4/2.6
   mem=[]
   for i in PM_col:
      if  re.search('memory', i):
         mem.append(i)
   # L2={i+' greater than 90 percent':['^9',PM_col.index(i)] for i in mem} ## not working in python 2.4/2.6
   L2={}
   for i in mem:
     L2[i+' > 90%']= ['^9[1-9]|^100',PM_col.index(i)]
   PM_err={'Failed Disks':['[1-9]',PM_col.index('Failed HDD')], 'Fan Failure':['f|F|Cr|cr',PM_col.index('Fan Status')],
   'Memory Failure ':['f|F|Cr|cr',PM_col.index('Memory Status')],'Power Failure ':['f|F|Cr|cr',PM_col.index('Power Status')],'Temperature Failure ':['f|F|Cr|cr',PM_col.index('Temp Status')],
   'Voltage Failure ':['f|F|Cr|cr',PM_col.index('Voltage Status')],'Batteries Failure ':['f|F|Cr|cr',PM_col.index('Batteries Status')],
   'NTP Error':['16',PM_col.index('NTP_strartum Status')], 'iDrac Not Connected':['No',PM_col.index('iDrac link connected')],'SCSI Errors(/var/log/messages)':['[1-9]',PM_col.index('SCSI_err')],
   'Disk Size(/opt) >90%':['^9[1-9]|^100',PM_col.index('Disk_Use(/opt)')],'Disk Size(/) >90%':['^9[1-9]|^100',PM_col.index('Disk_Use(/)')],'NTP Not Running':['^\s*$',PM_col.index('NTP_strartum Status')],
   'PM Database Not Running':['^(?!.*postgres)',PM_col.index('PM Postgres threads')],' PM Webservice Not Running':['^(?!.*httpd)',PM_col.index('PM Webservice threads')],
   'No. of DB connections > 90':['^9[1-9]|^1[0-9][0-9]',PM_col.index('Number of DB Connections')], 'nG1 Process Restart (Today)':['^(?!\s*$).*',PM_col.index('Process Restart(Today)')],
   'nG1 Process Restart (Yesterday)':['^(?!\s*$).*',PM_col.index('Process Restart(Yesterday)')],'IS Timeout (during past 24 hr)':['^(?!\s*$).*',PM_col.index('IS Timeout (During Past 24 hr)')],
   'PM Blackout (during today)':['^(?!\s*$).*',PM_col.index('PM Blackout (During Today)')],
   'Config Backup Not Generated Today':['^(?!(.*%s|NA))'%date_today,PM_col.index('Config_Backup Last Date')],
   'Paservice Restart':['^(?!\s*$).*',PM_col.index('Paservic Restart')]}
   PM_err.update(L2)
   
   PM_err_summ=get_error_summary(PM_err, pm_list_output) 
   print " PM error summary completed"
   

   ### Writing Link Status summary 
   if ln_status == 'Yes' or ln_status =='yes':
     write_link_summary(link_data,is_output,DIR,Voice_IS,is_ip,IS_col) ###(unsorted is_output)
   print  "Probes_Interface_link_status have been created"
   print PM_err_summ
   print IS_err_summ
   
   ####Wrting error Summary
   write_error(DIR+"/%s_Error_Summary.html"%(Deployment),PM_err_summ,IS_err_summ,is_list_output,IS_err,pm_list_output,PM_err)
   
   #### send email ###
   IS_collec=IS_data_collection (is_output,link_data,IS_col)
   PM_collec=PM_data_collection (pm_output, pm_input_list,PM_col)
   html=email_html(IS_collec,IS_err_summ, PM_collec, PM_err_summ,ln_status)
   print html
   send_email(To, From,DIR,ln_status,SMTP_IP,html)

   ### Reset the terminal
   os.popen("reset") 

def PM_link_thread(IP_list, Data,is_list):
    global Voice_IS
    for i in IP_list:
       print"GP: From within PM link thread :" + i
       PMs=i.split(",")
       if re.search('Local_PM', PMs[1]):
               get_link_data(PMs[0].rstrip(), Data,is_list,Voice_IS)
   
def IS_thread(List,link_data):
  global is_output
  for a in List:
     b= IS_ssh(a,link_data)
     if b:
       is_output[a]=b
def PM_thread(List):
   for line in List: 
      global pm_output 
      a= line.split(",")
      b=pm_local_ssh (str(a[0]),str(a[1]))
      if b: 
        pm_output[a[0]]=b
   
def get_error_summary(  R, L):
     ##Re={l:[] for l in R}not working in python 2.4/2.6
     
   
     Re={}
     for l in R:
       Re[l]=[]
     q=0
     for i in L:
       for j,k in R.items():
         print j
         print k
         print i[k[1]]
         if (re.search(k[0],i[k[1]])):
           Re[j].append(q)
           print Re
       q=q+1 
     return Re  
 
def  write_error (html,PM_err_summ,IS_err_summ,is_list_output,IS_err,pm_list_output,PM_err):
     f= open(html,'w')
     align='auto'
     width='35%'
     f.write(""" <!DOCTYPE html>
       <html>
       <body>
       <h1 style="color:red;font-family:verdana;"><u> %s Error Summary</u> </h1>
       <h3 style="font-family:verdana;"> Date: %s <h2>
              <style>
        table {
           border: 1px solid black;
           border-collapse: collapse;
           width: %s
           }
       td {
          border: 1px solid black;
          padding: 5px;
          text-align: %s;
          }
       tr {
         align:"center"
       }
       h2 {
          color :black
          
          }
       </style>
       """%(Deployment,ctime(),width,align))
     
     err_list=[PM_err_summ,IS_err_summ]
     for index,Re in enumerate(err_list): 
       if index==0:
          L=pm_list_output
          R=PM_err
          heading="PM Errors"

       else :
          L=is_list_output
          R=IS_err
          heading="IS Errors"

       f.write(""" <h2 style="color:red;font-family:verdana;"> %s </h2>""" %(heading))
     
       for b,c in Re.items():
         if c:
            f.write( """ <h2>%s (%s)</h2> """%(b,len(c)))
            f.write(""" <table> """)
            for d in c:
            
               f.write( "<tr align=justify><td>%s</td><td>%s</td><td> %s  </td> </tr>"%(L[d][0],L[d][1],L[d][R[b][1]]))
            
            f.write(""" </table>\n """)
            f.write("         ")
            
       if index==0:
            
            f.write("<br><br><hr>")
     f.write(" </body></html>  ")
     f.close()
     
def pm_local_ssh (j,d):
 global PM_t, PM_u, PM_s, Config_Backup
 PM_t=PM_t+1
 print d
 print j
 j= j.rstrip()
 d=d.rstrip()
 pm_output=[] 
 if re.search('.*:.*:.*:.*:.*',j):
    p1= subprocess.Popen(["ping6","-c","2",j], stdout=subprocess.PIPE)
    ip_status, err1 =p1.communicate()
    ip_status = re.findall('([0-9]) received',ip_status)
    ip_version='IPv6'
    if Ping_Disable:
       ip_status=[1]
    if int(ip_status[0]) > 0:
       #p2=subprocess.Popen(["timeout","20s","ssh","-6",j,"hostname"],stdout=subprocess.PIPE)
       #hostname,err2=p2.communicate()
       hostname=timeout_command(["ssh","-6",Login+'@'+j,"hostname"],60)
 else :
    p1= subprocess.Popen(["ping","-c","2",j], stdout=subprocess.PIPE)
    ip_status, err1 =p1.communicate()
    ip_status = re.findall('([0-9]) received',ip_status)
    ip_version='IPv4'
    if Ping_Disable:
       ip_status=[1]
    if int(ip_status[0]) > 0:
       #p2=subprocess.Popen(["timeout","20s","ssh",j,"hostname"],stdout=subprocess.PIPE)
       #hostname,err2=p2.communicate()
       hostname=timeout_command(["ssh",Login+'@'+j,"hostname"],60)
 if int(ip_status[0]) > 0 and hostname:
    ##if d == 'GPM':
    if re.search('GPM',d):
     comm= [ """ hostname """,
     
            """ cat /etc/sysconfig/network-scripts/ifcfg-eth0|grep -i ipaddr |cut -d= -f2 """,
            """ echo '%s' """%d,
            """ uptime |awk -F, '{print $1}' """,
            """ grep -i processor /proc/cpuinfo |wc -l """,
            """ cat /proc/meminfo |grep MemTotal|grep -o -e "[0-9].*[0-9]" """,
            """ sudo /usr/sbin/dmidecode -s system-serial-number """,
            """ uname -a |cut -d' ' -f3 """,
            """ cat /etc/redhat-release """,
            """ sudo cat /opt/NetScout/rtm/pa/bin/decoderelease.properties|grep -o "[1-9].*" """,
            """ sudo ntpq -pn |grep u|awk '{print $1}' |tr '\\n' ';' """,
            """ sudo ntpq -pn |grep u|awk '{print $3}' |tr '\\n' ';' """,
            """ sudo ntpq -pn |grep u|awk '{print $8}' |tr '\\n' ';' """,
            """ omreport storage pdisk controller=0 |grep "^State"|wc -l """,
            """ omreport storage pdisk controller=0 |grep "^State"| grep Failed |wc -l """,
            """ omreport chassis |grep -i Fans |cut -d' ' -f1 """,
            """ omreport chassis |grep -i Memory |cut -d' ' -f1 """,
            """ omreport chassis |grep -i "Power Supplies" |cut -d' ' -f1 """,
            """ omreport chassis |grep -i Temperatures |cut -d' ' -f1 """,
            """ omreport chassis |grep -i Voltages |cut -d' ' -f1 """,
            """ omreport chassis |grep -i Batteries |cut -d' ' -f1 """,
            """ sudo sar | awk '{print $9}'|grep "[0-9].*" |sort|head -1| awk '{x=100-$0};END{print x}' """,
            """ omreport system summary | grep -i version| head -1|cut -d: -f2 """,
            """ sudo /opt/dell/srvadmin/sbin/racadm getversion |grep -i iDRAC| cut -d= -f2 """,
            """ sudo /opt/dell/srvadmin/sbin/racadm getniccfg | grep "IP Address"|head -n 1|cut -d= -f2 """,
            """ sudo /opt/dell/srvadmin/sbin/racadm getniccfg | grep "Link Detected"|cut -d= -f2 """,
            """ df | grep opt|awk '{print $2/1073741824}' """,
            """ df -h |grep opt|grep -o "[0-9]*%" """,
            """ df -h |grep "/$"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/memorylog-globalm-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4|  grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ sudo cat /opt/NetScout/rtm/log/nssituationmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ echo "N/A" """,
            """ sudo /opt/NetScout/rtm/bin/PS|grep postgres """,
            """ sudo /opt/NetScout/rtm/bin/PS|grep http """,
            """ sudo ps -ef | grep pgsql_stealth_db | wc -l """,
            """ sudo -u ngenius -H sh -c "cd /opt/NetScout/rtm/log;find *$( date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt -mtime -1|xargs grep -i \\"debug ini\\"|sed -n  's/\\(.*\\)debuglog.*\\(\\[.*\\].*Debug\\).*/ \\1 \\2/p'|grep -o ".*]"" """,
            """ sudo -u ngenius -H sh -c "cd /opt/NetScout/rtm/log;find *$( date --date="yesterday" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt -mtime -1|xargs grep -i \\"debug ini\\"|sed -n  's/\\(.*\\)debuglog.*\\(\\[.*\\].*Debug\\).*/ \\1 \\2/p'|grep -o ".*]"" """,
            """ sudo /opt/NetScout/rtm/bin/PS|grep ngenius |awk '{print $7 }'|tr '\\n' ' '""",
            """ echo " " """,
            """ sudo -u ngenius -H sh -c "cd /opt/NetScout/rtm/log;grep -i \\"isBlackOut = true\\"  debuglog-$( date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt |grep WebxRemoteRequestDispatcherService | sed -n 's/.*Server :\\( .*\\)RMI.*/\\1/p'|uniq" """,
            """ sudo -u ngenius -H sh -c "cd /opt/NetScout/rtm/database/config-backup; ls -Art | tail -1|xargs stat| grep Change |sed -n 's/Change:\\(.*-[0-9][0-9]-[0-9][0-9]\\).*/\\1/p'" """,
            """ sudo grep "Sense code: .*" /var/log/messages |wc -l""",
            """ sudo grep "Request to start paservice received" /opt/NetScout/rtm/log/paservice_$( date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').log"""]
            
    else : 
      comm= [ """ hostname """,
            """ cat /etc/sysconfig/network-scripts/ifcfg-eth0|grep -i ipaddr |cut -d= -f2 """,
            """ echo '%s' """%d,
            """ uptime |awk -F, '{print $1}' """,
            """ grep -i processor /proc/cpuinfo |wc -l """,
            """ cat /proc/meminfo |grep MemTotal|grep -o -e "[0-9].*[0-9]" """,
            """ sudo /usr/sbin/dmidecode  -s system-serial-number """,
            """ uname -a |cut -d' ' -f3 """,
            """ cat /etc/redhat-release """,
            """ sudo cat /opt/NetScout/rtm/pa/bin/decoderelease.properties|grep -o "[1-9].*" """,
            """ sudo ntpq -pn |grep u|awk '{print $1}'|tr '\\n' ';'  """,
            """ sudo ntpq -pn |grep u|awk '{print $3}'|tr '\\n' ';'  """,
            """ sudo ntpq -pn |grep u|awk '{print $8}'|tr '\\n' ';'  """,
            """ omreport storage pdisk controller=0 |grep "^State"|wc -l """,
            """ omreport storage pdisk controller=0 |grep "^State"| grep Failed |wc -l """,
            """ omreport chassis |grep -i Fans |cut -d' ' -f1 """,
            """ omreport chassis |grep -i Memory |cut -d' ' -f1 """,
            """ omreport chassis |grep -i "Power Supplies" |cut -d' ' -f1 """,
            """ omreport chassis |grep -i Temperatures |cut -d' ' -f1 """,
            """ omreport chassis |grep -i Voltages |cut -d' ' -f1 """,
            """ omreport chassis |grep -i Batteries |cut -d' ' -f1 """,
            """ sar | awk '{print $9}'|grep "[0-9].*" |sort|head -1| awk '{x=100-$0};END{print x}' """,
            """ omreport system summary | grep -i version| head -1|cut -d: -f2 """,
            """ sudo /opt/dell/srvadmin/sbin/racadm getversion |grep iDRAC| cut -d= -f2 """,
            """ sudo /opt/dell/srvadmin/sbin/racadm getniccfg | grep "IP Address"|head -n 1|cut -d= -f2 """,
            """ sudo /opt/dell/srvadmin/sbin/racadm getniccfg | grep "Link Detected"|cut -d= -f2 """,
            """ df | grep opt|awk '{print $2/1073741824}' """,
            """ df -h |grep opt|grep -o "[0-9]*%" """,
            """ df -h |grep "/$"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/memorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4|  grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/asi2xwarehousememorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 | cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/asi2xservicewarehousememorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4|  grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/webxpresentmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4|  grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/uccontentmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 | cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/loggermemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4|  grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/flowloggermemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 | cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/fdsindexingmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 | cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/asi2xloggermemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 | cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/analyticsmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 | cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/whmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 | cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/webxreportgenmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4|  grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/flowrollupmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/nssituationmemorylog-$(date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|tail -1 |cut -d, -f4| grep -o "(.*)"|grep -o "[0-9]*%" """,
            """ sudo cat /opt/NetScout/rtm/log/flowloggerdebuglog-$(date --date="yesterday" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|grep total.*flows |cut -d= -f2|awk 'ORS=NR%4?" ":"\\n"'|awk '{print $1+$2+$3+$4}'|sort -n|tail -1 """,
            """ sudo cat /opt/NetScout/rtm/log/asi2xloggerdebuglog-$(date --date="yesterday" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt| grep DBONEStatsCollector:WRITE:AGGREGATED|grep -o "writtenRows=[0-9]*"|cut -d= -f2|sort -n |tail -1 """ ,
            """ sudo cat /opt/NetScout/rtm/log/asi2xloggereventlog-$(date --date="yesterday" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt|grep -o "totalPollCycleTime=[0-9]*"|cut -d= -f2|sort -n |tail -1""",
            """ sudo /opt/NetScout/rtm/bin/PS|grep postgres """,
            """ sudo /opt/NetScout/rtm/bin/PS|grep http """,
            """  ps -ef | grep pgsql_stealth_db | wc -l """,
            """ sudo -u ngenius -H sh -c "cd /opt/NetScout/rtm/log;find *$( date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt -mtime -1|xargs grep -i \\"debug ini\\"|sed -n  's/\\(.*\\)debuglog.*\\(\\[.*\\].*Debug\\).*/ \\1 \\2/p'|grep -o ".*]"" """,
            """  sudo -u ngenius -H sh -c "cd /opt/NetScout/rtm/log;find *$( date --date="yesterday" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').txt -mtime -1|xargs grep -i \\"debug ini\\"|sed -n  's/\\(.*\\)debuglog.*\\(\\[.*\\].*Debug\\).*/ \\1 \\2/p'|grep -o ".*]"" """,
            """ sudo /opt/NetScout/rtm/bin/PS|grep ngenius |awk '{print $7 }'|tr '\\n' ' '""",
            """ sudo find /opt/NetScout/rtm/log -mtime -2 -name "asi2xloggerxerrorlog-*"|xargs sudo grep \"timed out\" |sed -n 's/.*\\/\\([1-9].*\\):.*/\\1/p'|sort|uniq """,
            """ echo " " """,
            """ sudo -u ngenius -H sh -c "cd /opt/NetScout/rtm/database/config-backup; ls -Art | tail -1|xargs stat| grep Change |sed -n 's/Change:\\(.*-[0-9][0-9]-[0-9][0-9]\\).*/\\1/p'" """,
            """ sudo grep "Sense code:.*" /var/log/messages |wc -l""" ,
            """ sudo grep "Request to start paservice received" /opt/NetScout/rtm/log/paservice_$( date --date="today" |awk '{print $1}'|tr '[:upper:]' '[:lower:]').log"""           ]
                  
  
    command =''
    count=0
    for i in comm:
        if count < len(comm)-1:
            command=command+i+""" ; echo --;"""
        else:
            command=command+i
        count+=1
    if ip_version == 'IPv6':
       p= subprocess.Popen(["ssh" ,"-6","-t",Login+'@'+j,command], stdout=subprocess.PIPE)
       output,err= p.communicate()
 
    else :
       p= subprocess.Popen(["ssh","-t","-t",Login+'@'+j,command], stdout=subprocess.PIPE)
       output,err= p.communicate()
    print output
    if re.search('\r',output):
       pm_output=output.split("--\r\n")
    else: 
       pm_output=output.split("--\n")
    print pm_output
    for i in range(0,len(pm_output)):
      pm_output[i]=pm_output[i].rstrip()
    
    pm_output[1]=j  
 
 elif int(ip_status[0]) == 0:
     
     PM_u=PM_u+1
     PM_l.append(j)
 elif not hostname:
    PM_s.append(j)
 
 return pm_output
 
def IS_ssh (j,link_data):
 print j
 global IS_t , IS_u, IS_l,IS_s
 IS_t=IS_t+1
 j= j.rstrip()
 is_output=[] 
 if re.search('.*:.*:.*:.*:.*',j):
    #p1= subprocess.Popen(["ping6","-c","2",j], stdout=subprocess.PIPE)
    p1= subprocess.Popen(["ping6","-c","2",j], stdout=open(DIR+"/ipv6.txt",'w'))
    ip_status, err1 =p1.communicate()
    ip_status = re.findall('([0-9]) received',ip_status)
    ip_version='IPv6'
    if Ping_Disable:
       ip_status=[1]
    if int(ip_status[0]) > 0:
       #p2=subprocess.Popen(["timeout","20s","ssh","-6",j,"hostname"],stdout=subprocess.PIPE)
       #hostname,err2=p2.communicate()
       hostname=timeout_command(["ssh","-6",Login+'@'+j,"hostname"],60)
 else :
    p1= subprocess.Popen(["ping","-c","2",j], stdout=subprocess.PIPE)
    ip_status, err1 =p1.communicate()
    ip_status = re.findall('([0-9]) received',ip_status)
    ip_version='IPv4'
    if Ping_Disable:
       ip_status=[1]
    if int(ip_status[0]) > 0:
         #p2=subprocess.Popen(["timeout","20s","ssh",j,"hostname"],stdout=subprocess.PIPE)
         #hostname,err2=p2.communicate()
         hostname=timeout_command(["ssh",Login+'@'+j,"hostname"],60)
 if int(ip_status[0]) > 0 and hostname:
 
    comm= [ """ hostname """,
     """ cat /etc/sysconfig/network-scripts/ifcfg-eth0|grep -i ipaddr |cut -d= -f2 """,
     """ date """,
     """ sudo hwclock """,
     """ sudo ipmitool lan print |grep -i "IP Address"| tail -1| cut -d: -f2 """,
     """ pkill -9 localconsole;echo -e "11\\nget agent\\nexit\\n"| sudo /opt/NetScout/rtm/bin/localconsole| grep model_number|awk '{print $3}' """,
     """  echo -e "11\\nget agent\\nexit\\n"| sudo /opt/NetScout/rtm/bin/localconsole| grep software_version| awk '{print $2,$3,$4,$5}' """,
     """ echo -e "11\\n get asi_mode \\nexit\\n"| sudo /opt/NetScout/rtm/bin/localconsole|grep asi_mode|sed -n 's/.*set.*to*\\(.*\\)/\\1/p' """,
     """  echo -e "11\\nget agent\\nexit\\n"| sudo /opt/NetScout/rtm/bin/localconsole| grep serial|head -1|awk '{print $2}' """, ##
     """ uname -a |cut -d' ' -f3 """,
     """ grep -i processor /proc/cpuinfo |wc -l """,
     """ cat /proc/meminfo |grep MemTotal|grep -o -e "[0-9].*[0-9]" """,
     """ uptime |awk -F, '{print $1}' """,
     """ uptime |grep -o load.*|cut -d: -f2 """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*" | tail -n 2 | head -n 1 |xargs cat|grep "Data.*Array"|sort|uniq|wc -l """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*"| tail -n 2 | head -n 1 |xargs cat|grep Disk| sort|uniq|wc -l """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*"| tail -n 2 | head -n 1 |xargs cat|grep Disk|grep -e "FAILED" -e "AVAILABLE" -e "MISSING" |sort| uniq |wc -l """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*" | tail -n 2 | head -n 1 |xargs cat|grep Disk|grep -e "FAILED" -e "AVAILABLE" -e "MISSING" |sort| uniq|grep -o -e " Infin.* Disk" -e " ESU.* Disk"|awk '{print $1,$3,$4}' |awk {print} ORS=" ," """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*"| tail -n 2 | head -n 1 |xargs cat|grep Disk|grep -i "FAILING"|sort| uniq |wc -l """,    
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*" | tail -n 2 | head -n 1 |xargs cat|grep Disk|grep -i "FOREIGN"|sort| uniq |wc -l """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*" | tail -n 2 | head -n 1 |xargs cat|grep "FAN STATUS"|sort|uniq|head -n 1| awk '{print$7}' """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*" | tail -n 2 | head -n 1 |xargs cat|grep "POWER SUPPLY STATUS"|sort|uniq|head -n 1| awk '{print$9}' """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*" | tail -n 2 | head -n 1 |xargs cat|grep "TEMPERATURE STATUS"|sort|uniq|head -n 1| awk '{print$8}' """,
     """ sudo sh -c "ls -Art /opt/platform/nshwmon/log/nshwmon-logfiles/nshwmon*" | tail -n 2 | head -n 1 |xargs cat|grep "VOLTAGE STATUS"|sort|uniq|head -n 1| awk '{print$8}' """,
     """ sudo sh -c "ntpq -pn" |grep u|awk '{print $1}'|tr '\\n' ';'  """,
     """ sudo sh -c "ntpq -pn" |grep u|awk '{print $3}'|tr '\\n' ';'  """,
     """ sudo sh -c "ntpq -pn" |grep u|awk '{print $8}'|tr '\\n' ';'  """,
     """ sudo find /core -mtime -2 -name "core.*" |wc -l """,
     """ sudo sh -c "ethtool eth0" |grep Duplex |cut -d: -f2 """,
     """ df -h |grep / |head -1| awk '{print $5}' """,
     """ df -h |grep metadata|grep -o "[0-9]*%" """,
     """ df -h |grep xdr|grep -o "[0-9]*%" """,
     """ df -h| grep xdr |awk '{print $2}' """,
     """ sudo stat /xdr/*/$(ls -t /xdr|head -1|xargs -i ls -t /xdr/{}|tail -1)|grep ..:..:..|head -1|cut -d: -f2,3""",
     """ echo `sudo /opt/NetScout/rtm/tools/printva |grep DataSize|cut -d: -f3|sed -n 's/\\(.*\\)GB.*/\\1/p'`""",
     """ sudo pkill -9 localconsole;echo -e  "exit\\n" | sudo /opt/NetScout/rtm/bin/localconsole|grep "Server Add" |sed -n 's/.*Address\\(.*\\)/\\1/p' """,
     """ echo -e "15\nexit\n"| sudo /opt/NetScout/rtm/bin/localconsole|grep "Voice and Video Quality"|sed -n 's/.*Quality.*\\(o.*\\)/\\1/p' """,
     """ echo -e  "11\\nget agent\\nexit\\n" | sudo /opt/NetScout/rtm/bin/localconsole|grep "memory size"|awk '{print $3}' """,
     """ echo -e  "11\\n get dump free_mem\\nexit\\n" | sudo /opt/NetScout/rtm/bin/localconsole|grep Free|cut -d= -f2|grep -o .*[0-9] """,
     """ echo -e "11\\n get table_size_allocation ctrl \\nexit\\n"| sudo /opt/NetScout/rtm/bin/localconsole| grep -A6 "Ifn.*Percentage" | grep -v -e Ifn -e "^\s*$" -e "%"|awk '{print $1,$2,$3,$4}' OFS=- ORS=";" """,
     """ echo -e "11\\n get dump sysuptime\\nexit\\n"| sudo /opt/NetScout/rtm/bin/localconsole""",
     """ sudo /opt/NetScout/rtm/bin/PS| sed -n 2,15p|awk  '{print $7}' |tr '\\n' ' ' """,
     """ echo -e  "11\\n set auto_scroll on\\nget dump tables\\nexit\\n" | sudo /opt/NetScout/rtm/bin/localconsole |grep ".:.*:.*"|grep -e "`date +%m-%d-%Y`" -e `date --date="yesterday" +%m-%d-%Y`|sed  's/- ses/ses/p'|uniq |awk '{print $1,$2,$6}' OFS=: ORS=",   \n" """ ]
    ### For packet retention
    comm.append(""" sudo /opt/NetScout/rtm/tools/printstore -pkt|head -20| sed -n 7,20p |grep  m*Time""" )
    ### For Erros in /var/log messages "USB, XDR, SATA"
    comm.append(""" sudo grep -e "couldn't allocate port*usb_device" -e "XFS_WANT_CORRUPTED_RETURN" -e "SATA" /var/log/messages""" )
    ### Dengine greater than 8 hour
    comm.append(""" sudo ps -eo pid,etime,comm | awk '{if($2~/-.*:.*:/ || $2~/0?[8-9]:.*:.*/ || $2~/[1-2][0-9]:.*:.*/) print $2,$3}'|grep dengine """)
    If_comm=''
    sip_comm=''
    gtp_corr_comm=''
    vifn_mode_comm=''
    Tcm_conn_comm=''
    if j in link_data:
       for interface in link_data[j]['IF']:
             sip= """ echo "if_%s:"|tr '\\n' ' '; echo -e "11\\n get dump mobile_tables %s\\nexit\\n"|sudo /opt/NetScout/rtm/bin/localconsole|grep -o ses_sip_db.*|awk '{print $ 3,$5,$6,$10}' OFS=',';"""%(interface,interface)
             If= """ echo "if_%s"|tr '\\n' ':';echo -e  "11\\nset curr_interface %s\\nget interface_options %s\\nexit\\n" | sudo /opt/NetScout/rtm/bin/localconsole|grep -i "interface type"|awk '{print $4}';"""%(interface,interface,interface)
             gtp_corr=""" echo "if_%s"|tr '\\n' ':';echo -e  "11\\nget dump scn %s \\nexit\\n" | sudo /opt/NetScout/rtm/bin/localconsole|grep -i "TOT_NON_CORRELATED_DATA_PKTS:"|grep -o GTPv2.*|awk '{print $5}';echo -e "\\n" ;"""%(interface,interface)
             vifn_mode= """ echo "if_%s"|tr '\\n' ':';echo -e  "11\\nset curr_interface %s\\nget interface_options %s\\nexit\\n" | sudo /opt/NetScout/rtm/bin/localconsole|grep -i "vifn_mode"|awk '{print $3}';"""%(interface,interface,interface)
             Tcm_conn= """echo "if_%s"|tr '\\n' ':';echo -e "11\\nget dump tcm %s\\nexit\\n"|sudo /opt/NetScout/rtm/bin/localconsole|grep "TCM connection shortage"|awk '{print $4}';"""%(interface,interface)
             If_comm+=If
             sip_comm+=sip
             gtp_corr_comm+=gtp_corr
             vifn_mode_comm+=vifn_mode
             Tcm_conn_comm+=Tcm_conn

       comm.append(If_comm[:-1])  
       comm.append(sip_comm[:-1])
       comm.append(gtp_corr_comm[:-1])
       comm.append(vifn_mode_comm[:-1])
       comm.append(Tcm_conn_comm[:-1])
    else:
       comm.append(""" echo NA """)
       comm.append(""" echo NA """)
       comm.append(""" echo NA """)
       comm.append(""" echo NA """)
       comm.append(""" echo NA """)


    command =''
    count=0
    for i in comm:
        if count < len(comm)-1:
            command=command+i+""" ; echo --;"""  ### appending 
        else:
            command=command+i
        count+=1
    if ip_version == 'IPv6':
       p= subprocess.Popen(["ssh","-6","-t",Login+'@'+j,command], stdout=subprocess.PIPE)
       output,err= p.communicate()
    else :
       print "Start Printing Command...."
       print >> sys.stderr, command
       print ".... End Printing Command"
       p= subprocess.Popen(["ssh","-t","-t",Login+'@'+j,command], stdout=subprocess.PIPE)
       output,err= p.communicate()
    print output
    
    if re.search('\r',output):
       is_output=output.split("--\r\n")
    else: 
       is_output=output.split("--\n")
    print is_output
    for i in range(0,len(is_output)):
           is_output[i]=is_output[i].rstrip()
    
    is_output[1]=j      
 elif int(ip_status[0]) == 0:
     
     IS_u=IS_u+1
     IS_l.append(j)
 elif not hostname:
    IS_s.append(j)
 
 return is_output

def send_email(To, From,DIR,ln_status,SMTP_IP,html):
 global Deployment
 msg = MIMEMultipart('alternative')
 msg['Subject'] = subject
 msg['From'] = From
 msg['To'] = ",".join(To)
 time= ctime()


 part2 = MIMEText(html, 'html')


 
 fp= open(DIR+"/%s_PM_Healthcheck.csv"%(Deployment), 'rb')
 a=fp.read().rstrip()
 part1 = MIMEText(a)
 fp.close()
 part1.add_header('Content-Disposition', 'attachment', filename="%s_PM_Healthcheck.csv"%Deployment) 
 
 fp= open(DIR+"/%s_IS_Healthcheck.csv"%(Deployment), 'rb')
 a=fp.read().rstrip()
 part3 = MIMEText(a)
 fp.close()
 part3.add_header('Content-Disposition', 'attachment', filename="%s_IS_Healthcheck.csv"%Deployment) 
 
 fp= open(DIR+"/%s_Error_Summary.html"%(Deployment), 'rb')
 a=fp.read().rstrip()
 part4 = MIMEText(a)
 fp.close()
 part4.add_header('Content-Disposition', 'attachment', filename="%s_Error_Summary.html"%Deployment) 
 
 
 msg.attach(part1)
 msg.attach(part2)
 msg.attach(part3)
 msg.attach(part4)
 #msg.attach(part5)

 if ln_status == 'Yes' or ln_status == 'yes':
       
       fp= open(DIR+"/%s_IS_Interface_Stats.html"%(Deployment), 'rb')
       a=fp.read().rstrip()
       if sys.version[0:3]=='2.4':
          part6 = MIMEText(a)
          fp.close()
          part6.add_header('Content-Disposition', 'attachment', filename="%s_IS_Interface_Stats.html"%Deployment) 
       else:
          from email.mime.application import MIMEApplication
          part6 = MIMEApplication(a)
          fp.close()
          #part6.add_header('Content-Disposition', 'attachment', filename="%s_IS_link_table_status.html"%Deployment) 
          part6['Content-Disposition'] = 'attachment; filename="%s_IS_Interface_Stats.html"'%Deployment    
          
       msg.attach(part6)
 
 s = smtplib.SMTP(SMTP_IP)
 s.sendmail(From, To, msg.as_string())

 s.quit()

def write_link_summary(Data,is_output,DIR,Voice_IS,is_ip,IS_col): 
   global Deployment
   ###Interface Counts
   IF_count=0
   IS_unacc=[]
   for ip in is_output:
     if ip in Data:
        IF_count=IF_count+len(Data[ip]['IF'])
     if ip not in Data:
         IS_unacc.append(is_output[ip][0])
        
   
   html= """ <h1 style="color:brown;font-size:200%"> Infinistream Interface Performance Stats </h1> """
   html+= """ <h2> Date: %s</h2> """%ctime()
   html+= """ <h2 style="font-size:90%"> **** Link Utilizations are collected from hourly_vital_stats table, with 1 hr resolution, from each local PMs. </h2> """
   html+= """ <h2 style="font-size:90%"> **** Total Memory, Free Memory ,Table Size Allocation and Table Drops data are taken from Infinistreams output.  </h2> """
   html+= """ <h2 style="font-size:90%"> **** Total Peak PPS per probe, Peak Packet drops per probe , and Peak Active-Streams per probe are the sum of individual values of the interfaces.  </h2> """
   html+= """ <h2 style="font-size:90%"> **** Background cell color turns red if Dropped Packets > 0, PPS(K) =0 or Table drops is 'Yes'.</h2> """
   html+= """ <h2 style="font-size:90%"> **** Peak Packet Drops % = (Dropped packets at Peak PPS/(Total packets in peak hr+ Dropped packets at Peak PPS))*100 </h2> """
   html+= """ <h2 style="font-size:90%"> **** Peak Dropped Packets is the peak value in last 24 hour, and may or may not be the same as <b>Dropped packets at Peak PPS</b></h2>  """
   html+= """ <h2 style="font-size:90%%"> **** Total Infinistreams :%s, Total Interfaces :%s</h2> """%(len(Data),IF_count)
   if IS_unacc:
      html+= """ <h2 style="font-size:90%%"> **** Infinistreams not accounted:%s</h2> """%(str(IS_unacc).strip('[]').replace('\'',''))

   html+= """ <table border="2" style="width:70%"> """
   html+=""" <tr> <th>Probe IP</th><th>Server IP</th><th>Model</th><th>Software Version</th><th>CPUs</th><th>Total Physical Memory (GB)</th> <th>nsprobe Memory (MB)\
     </th><th>Free Memory (Bytes)</th><th>Interface</th><th>Interface_type</th><th>Vifn_mode</th><th>Last 24 hr Peak Link Utilization (Gbps) </th><th>Last 24 hr Peak PPS(K) </th> \
     <th>Peak_PPS_Time (last 24 hr)</th><th> Dropped Packets at peak PPS </th><th> Peak Packet Drops % (1 hr res) </th></th><th> Peak Dropped Packets (in last 24 hr)</th><th>Last hour PPS (K)</th> """
   if Voice_IS:
     html+= """<th>Peak Active-Streams (K)</th>"""
   if GTPv2_DATA_Corr:
     html+= """<th>Gtpv2 Non Correlated Data (%)</th>"""
   html+="""<th>Table_Size_Alloc (ifn-size-ctrl-data)</th><th>Table Drops (Yest to Curr)</th>"""
   if S1MME:
     html+="""<th>S1 NAS Deciphering Rate(%)</th>"""
   if Deployment=='IMS':
     html+= """<th>Max Current Sessions(sip_db)</th><th>Max Active Sessions(sip_db)</th><th>Max Configured Sessions(sip_db)</th><th>Total sip_db Drops </th><th>Total Max Currrent Sessions(sip_db) </th> """ ##For IMS
   html+="""<th>Total Peak PPS Per Probe """
   if Voice_IS:
     html+="""</th><th>Total Peak Active-Streams (K)Per Probe  </th>"""
   html+="""<th>Total Peak Packet Drops Per Probe  </th>"""
   
   ##else:
   ##  html+= """ <tr> <th>Probe IP</th><th>Server IP</th><th>Model</th><th>Software Version</th><th>CPUs</th><th>Total Physical Memory (GB)</th> <th>nsprobe Memory (MB)</th><th>Free Memory (Bytes)</th><th>Interface</th><th>Interface_type</th><th>Last 24 hr Peak Link Utilization (Gbps) </th><th>Last 24 hr Peak PPS(K)</th> \
   ##  <th>Peak_PPS_Time (last 24 hr)</th></th><th> Dropped Packets (peak value in last 24 hr)</th><th>Last hour PPS (K)</th><th>Table_Size_Alloc (ifn-size-ctrl-data)</th><th>Table Drops (Yest to Curr)</th>"""
   ##  ##html+= """<th>Max Current Sessions(sip_db)</th><th>Max Active Sessions(sip_db)</th><th>Max Configured Sessions(sip_db)</th><th>Total sip_db Drops </th><th>Total Max Currrent Sessions(sip_db) </th> """ ## For IMS
   ##  html+= """<th>Total Peak PPS Per Probe  </th><th>Total Peak Packet Drops Per Probe  </th>"""      
   for i in is_ip:
      a=1
      if i in Data:
         hostname=is_output[i][IS_col.index('Hostname')] ### Host name ##
         total_mem=round(int(is_output[i][IS_col.index('Memory')])/float(1000000),3)  ### Total IS memory    
         server_IP= is_output[i][IS_col.index('PM Server')] ###Server Address
         nsprobe_mem= is_output[i][IS_col.index('Nsprobe Mem')] ### nsprobe Mem
         free_mem= is_output[i][IS_col.index('Free_Mem')]  ### IS Free memory
         table_size_allocation=is_output[i][IS_col.index('Table_Size_Allocation(ifn-size-ctrl-data)')] ### Table_size_allocation
         table_drops=is_output[i][IS_col.index('Table_Drops (Yesterday to Current)')] ### Table drops
         Interface_type=is_output[i][IS_col.index('Interface_Type')] ### Interface Type
         cpu=is_output[i][IS_col.index('CPU')] ### CPUs
         sw_version=is_output[i][IS_col.index('Version')] ### Software version
         model=is_output[i][IS_col.index('Model')] ### Model Number
         sip_db_out=is_output[i][IS_col.index('Sip_db')]
         gtp_corr=is_output[i][IS_col.index('GTPv2_corr')]
         vifn_mode=is_output[i][IS_col.index('Vifn_mode')]
         if S1MME:
           s1_nas=is_output[i][IS_col.index('NAS_Deciphering rate %')]
      #else:
      #   hostname="NA"
      #   total_mem="NA"
      #   server_IP="NA"
      #   nsprobe_mem="NA"
      #   free_mem="NA"
      #   table_drops="NA"
      #   table_size_allocation="NA"
      #   Interface_type="NA"
      #   cpu="NA"
      #   sw_version="NA"
      #   model="NA"
      #   #sip_db_out="NA"
      #   gtp_corr="NA"
         
      #####  Total sip_db Max_session per box
         if sip_db_out != 'NA':
            sess=re.findall('if_.*:(.*),.*,.*,.*',sip_db_out)
            total_sess=0
            for n in sess:
                total_sess+=int(n)
         else:
             total_sess='NA'
      
         total_pps=0
         total_pkts=0
         total_pkt_drops=0
         total_streams=0
         #pkt_drops_pct=0

         for dt in Data[i]['IF']:
             
                 link_data=Data[i]['data_'+dt]
                 total_pps+=link_data[1]
                 total_pkt_drops+=int(link_data[4])
                 total_pkts+=(link_data[7])
                 if Voice_IS:
                     if re.search('[0-9]',str(link_data[6])):
                        total_streams+=float(link_data[6])
         #if total_pkt_drops and total_pkts:
         #      pkt_drops_pct=total_pkt_drops/float(tot_pkts+)
         ### IP, Total memory and Free Memory
         html+=""" <tr>
          <th rowspan="%s">%s-%s</th>
          <th rowspan="%s">%s</th>       
          <th rowspan="%s">%s</th> 
          <th rowspan="%s">%s</th>
          <th rowspan="%s">%s</th>
          <th rowspan="%s">%s</th>
          <th rowspan="%s">%s</th>
          <th rowspan="%s">%s</th> """  %(len(Data[i]['IF']),hostname,i,len(Data[i]['IF']),server_IP,len(Data[i]['IF']),model,len(Data[i]['IF']),sw_version,len(Data[i]['IF']),cpu,len(Data[i]['IF']),total_mem,len(Data[i]['IF']),nsprobe_mem,len(Data[i]['IF']),free_mem)
         
         for j in Data[i]['IF']:
                 if_table_size_list=[ts for ts in table_size_allocation.split(";") if re.search('^%s'%j,ts)]
                 #if_table_drops_list=[td for td in table_drops.split("\n") if re.search('^%s'%j,td)]
                 if_table_drops_list=re.findall('(%s:.*[a-zA-Z]):.*:.*'%j,table_drops)
                 if_type=re.findall('if_%s:(.*)'%j,Interface_type)
                 if_vifn_mode=re.findall('if_%s:(.*)'%j,vifn_mode)
                 if_table_size=''
                 if_table_drops=''
                 
                       
                           
                           
                 if a != 1:
                    html+="<tr>"
                 html+="<td> If:%s </td>"%j
                 if Interface_type !="NA":
                    html+="<td> %s </td>"%if_type[0]
                 elif Interface_type =="NA":
                    html+="<td> NA </td>"
                 if vifn_mode !="NA":
                    html+="<td> %s </td>"%if_vifn_mode[0]
                 elif vifn_mode =="NA":
                    html+="<td> NA </td>"
                 #b=0
                 #### PPS and Link Utilization data per IF
                 vital_stats=Data[i]['data_'+j]
           
                 ### Link Util
                 html+="<td> %s </td>"%vital_stats[0]
                 ### 24 hr PPS
                 if vital_stats[1]==0.000:
                               html+="""<td BGCOLOR="red"> %s </td>"""%vital_stats[1]
                               html+="""<td> n/a</td>"""
                 else:
                               html+="""<td > %s </td>"""%vital_stats[1]
                               html+="""<td> %s</td>"""%vital_stats[2]

                 ### Dropped Packets at PPS             
                 if int(vital_stats[6]) !=0: 
                               html+="""<td BGCOLOR="red"> %s </td>"""%vital_stats[6]
                               #html+="""<td> %s </td>"""%vital_stats[5]
                               pkt_drops_pct= round(int(vital_stats[6])/float(vital_stats[8]+int(vital_stats[6])),4)
                               html+="""<td BGCOLOR="red"> %s </td>"""%pkt_drops_pct
                 else :
                               html+="""<td BGCOLOR="lightgreen"> %s </td>"""%vital_stats[6]
                               #html+="""<td> %n/a </td>"""
                               html+="""<td BGCOLOR="lightgreen"> 0 </td>"""
                 ### Dropped Packets              
                 if int(vital_stats[4]) !=0: 
                               html+="""<td BGCOLOR="red"> %s </td>"""%vital_stats[4]
                               #html+="""<td> %s </td>"""%vital_stats[5]
         
                 else :
                               html+="""<td BGCOLOR="lightgreen"> %s </td>"""%vital_stats[4]
                               #html+="""<td> %n/a </td>"""

                 ### Last hour PPS              
                 if vital_stats[3]==0.000:
                                html+="""<td BGCOLOR="red"> %s </td>"""%vital_stats[3]  
                 else:
                                html+="""<td > %s </td>"""%vital_stats[3]      
                 
                 
                 #### Active Streams
                 if Voice_IS:
                     if re.search('[0-9]',str(vital_stats[7])):
                                    html+="""<td> %s </td>"""%vital_stats[7]  
                     else:
                                html+="""<td> null </td>"""                  
                 #### GTP correlation
                 if GTPv2_DATA_Corr:
                     if gtp_corr != 'NA' or None:
                        try:
                          gtpv2_data_corr=re.findall('if_%s:((?:.*))'%j,gtp_corr)[0]
                        except:
                          gtpv2_data_corr='NA'
                        if gtpv2_data_corr:
                           html+="""<td> %s </td>""" %gtpv2_data_corr
                        else:
                           html+="""<td> NA </td>"""
                       
                     else:
                        html+="""<td> NA </td>""" 
                 #### Table_size_allocation cell
                 if if_table_size_list:
                    for l in if_table_size_list:
                        if_table_size+=l
                    if_table_size=if_table_size.replace(',',' ')
                    html+="""<td> %s </td>"""%if_table_size
                 else:
                    html+="""<td> None </td>"""    
                 ### Table_drops cell  
                 if if_table_drops_list:
                    for m in if_table_drops_list:
                        if_table_drops+=m+', ' 
                    html+="""<td BGCOLOR="red"> %s </td>"""%if_table_drops
                 else:
                    html+="""<td BGCOLOR="lightgreen"> None </td>""" 
                    
                 #### S1MME
                 if S1MME:
                   if_nas=re.findall('if_%s:([0-9].*)\''%j,s1_nas)
                   if if_nas:
                       nas_value=float(if_nas[0])
                       if nas_value < 80.0 :
                          html+="""<td BGCOLOR="red"> %s</td>""" %nas_value
                       else:
                          html+=""" <td BGCOLOR="lightgreen">%s</td>"""%nas_value
                   else:
                       html+= """ <td>NA</td>"""
                     
                    
                 ###### sip_db values  
                 if Deployment=='IMS':
                     if sip_db_out != 'NA':
                           sip_db_if=re.findall('(if_%s.*)'%j,sip_db_out)
                           
                           #if sip_db_if:
                           sip_db_if_value=sip_db_if[0].split(":")
                           print sip_db_if_value
                           if re.search('.*,.*,.*',sip_db_if_value[1]):
                              sip_entries=sip_db_if_value[1].split(",")
                              
                              for sip_i in sip_entries:
                                   html+= """<td> %s </td> """%sip_i
                           else:
                                 html+=""" <td> NA </td> <td> NA </td> <td> NA </td> <td> NA </td>"""
                            
                     else:
                          html+=""" <td> NA </td> <td> NA </td> <td> NA </td> <td> NA </td>"""
                 ### Total Max_cuur_session, Total PPS and Total Packet drops
                 if a==1:
                      if Deployment=='IMS':
                        html+="""<th rowspan="%s">%s</th> """%(len(Data[i]['IF']),total_sess) ###for total_sip sessions
                      html+="""<th rowspan="%s">%s</th> """%(len(Data[i]['IF']),total_pps)
                      if Voice_IS:
                        html+="""<th rowspan="%s">%s</th> """%(len(Data[i]['IF']),total_streams)
                      html+="""<th rowspan="%s">%s</th> """%(len(Data[i]['IF']),total_pkt_drops)
                  
                 ################
                 a+=1
                 html+="</tr>\n"
         
   html+="</table>"           
   file=open(DIR+"/%s_IS_Interface_Stats.html"%(Deployment),"wb")
   file.write(""" <!DOCTYPE html>
                   <html>
                   <body>
                   <style>
                   th{
                    align:"center"
                           }   
                   </style>    """)
   file.write(html)
   file.write(""" </body>
                   </html> """)
   print Data  

  
def get_link_data(PM_ip,Data,is_list,Voice_IS):


      ### Folder for input and output SQL files
      DIR=os.getcwd()+'/link_data'


      Link_Data={}
      IS_L=[]
      input_comm="""  sudo ls -l /opt/NetScout/rtm/database/dbone/$(date +%Y-%m-%d)/vitalstats-hourly|grep -v total|awk '{print $9}'|cut -d. -f1|awk -F- '{print $3,$4}' """
      output,err=ssh_command(PM_ip, input_comm)
    
      out_list=output.rstrip().split('\n')

      for i in out_list:
          j=i.split()
          print j
          if re.search('.*_.*_.*_.*_.*_.*_.*_.*',j[0]):
            ip=j[0].replace('_',':')
          else:
            ip=j[0].replace('_','.')
          if ip in is_list: ### to filter out IPs that are not IS file
            if ip not in IS_L:
                 IS_L.append(ip)
            if ip in Link_Data:
                     Link_Data[ip]['IF'].append(j[1])
                
            else:
                Link_Data.update({ip:{'IF':[]}})
                Link_Data[ip]['IF'].append(j[1])
               
      
      for i in IS_L:
          
  
          for j in Link_Data[i]['IF']:
             if re.search('.*\..*\..*\..*',i):
                    ip=i.replace(".","_")
             elif re.search('.*:.*:.*:.*:.*:.*:.*:.*',i):
                    ip=i.replace(":","_")
             
             SQL_comm="""sudo mkdir -p %s;"""%(DIR)
             SQL_comm+=""" echo "SELECT a.appid,a.targettime,a.pps,a.util,b.lh_pps FROM( SELECT appid,targettime, (vitalstats_packetsout+vitalstats_packetsin) as PPS,((vitalstats_octetsout+vitalstats_octetsin)/450000)as UTIL FROM hourly_vitalstats_%s_%s WHERE appid=184549377 ) a JOIN (SELECT appid,(vitalstats_packetsout+vitalstats_packetsin)as lh_pps FROM hourly_vitalstats_%s_%s WHERE appid=184549377 ORDER BY targettime DESC LIMIT 1 )b on a.appid=b.appid ORDER BY pps DESC LIMIT 1;" |sudo tee %s/input_pps_lu;"""%(ip,j,ip,j,DIR)
             SQL_comm+="""  echo "SELECT appid,targettime, (vitalstats_packetsout+vitalstats_packetsin)as Dp FROM hourly_vitalstats_%s_%s WHERE appid=184549384 ORDER BY Dp DESC LIMIT 1;" |sudo tee %s/input_dp;"""%(ip,j,DIR)
             SQL_comm+="""  echo "SELECT a.appid,a.targettime, a.Dp,b.pps FROM (  SELECT appid,targettime, (vitalstats_packetsout+vitalstats_packetsin) as Dp FROM hourly_vitalstats_%s_%s WHERE appid=184549384) a JOIN (SELECT appid,targettime,(vitalstats_packetsout+vitalstats_packetsin) as PPS FROM hourly_vitalstats_%s_%s WHERE appid=184549377) b on a.targettime=b.targettime order by b.pps DESC LIMIT 1;" |sudo tee %s/input_dp_peak_pps;"""%(ip,j,ip,j,DIR)
             SQL_comm+=""" sudo /opt/NetScout/rtm/bin/nGeniusSQL.sh %s/input_pps_lu %s/out_pps_lu_%s_%s; sudo /opt/NetScout/rtm/bin/nGeniusSQL.sh %s/input_dp %s/out_dp_%s_%s; sudo /opt/NetScout/rtm/bin/nGeniusSQL.sh %s/input_dp_peak_pps %s/out_dp_pps_%s_%s;"""%(DIR,DIR,ip,j,DIR,DIR,ip,j,DIR,DIR,ip,j)
             if Voice_IS:
                SQL_comm+="""  echo "SELECT MAX(sum)  FROM (SELECT sum(activestreamsin) FROM hourly_uc_kpi_%s_%s GROUP BY targettime) AS foo" |sudo tee %s/input_uckpi;"""%(ip,j,DIR)
                SQL_comm+=""" sudo /opt/NetScout/rtm/bin/nGeniusSQL.sh %s/input_uckpi %s/out_uckpi_%s_%s """%(DIR,DIR,ip,j)
             else: 
                SQL_comm+=""" echo "None" |sudo tee %s/out_uckpi_%s_%s """%(DIR,ip,j)
             SQL_output="""  grep 184549377 %s/out_pps_lu_%s_%s|awk -F, '{print $4,$3,$2,$5}' OFS=";"|tr "\n" ";";grep 184549384 %s/out_dp_%s_%s| awk -F, '{print $3,$2}' OFS=";"|tr "\n" ";";grep 184549384 %s/out_dp_pps_%s_%s| awk -F, '{print $3}' OFS=";"|tr "\n" ";";if [ -f %s/out_uckpi_%s_%s ]; then tail -1  %s/out_uckpi_%s_%s;fi """%(DIR,ip,j,DIR,ip,j,DIR,ip,j,DIR,ip,j,DIR,ip,j)
           
             out_p1,err1=ssh_command(PM_ip, SQL_comm)
             print out_p1
             output,err=ssh_command(PM_ip, SQL_output)
             print output
             data_out=output.rstrip().split(";")

             ## Total Packets
             tot_pkts=int(data_out[1])


             data_out[0]=round(int(data_out[0])/float(1000000),3) ##24 hr Link Util Gbps
             data_out[1]=round(int(data_out[1])/float(3600000),3) ### 24 hr peak pps (K)
             data_out[3]=round(int(data_out[3])/float(3600000),3)### Last hr peak pps (K)
            ## data_out[6] dropped packets at pps
             if re.search('[0-9]',data_out[6]):
                data_out[7]=round(int(data_out[6])/float(3600000),2) ### Active Streams 
             print data_out
             data_index='data_'+j
             #if tot_pkts:
             #   data_out.append(int(data_out[4])*100/float(tot_pkts+int(data_out[4])))
             #else :
             #     data_out.append(0)
             ## data_if:[ 24 hr Link Util Gbps, 24 hr peak pps (K), PPS time,Last hr peak pps (K),dropped packets, dropped packet time,dropped_packets_at_pps, active streams,total pkts]
             data_out.append(tot_pkts)
             Link_Data[i].update({data_index:data_out})
      Data.update(Link_Data)       


def ssh_command(IP, command):
    if re.search('.*\..*\..*\..*',IP):
       if int(os.popen('ping -c 2 %s|grep received | cut -d, -f2 |grep -o [0-9]'%IP).read().rstrip()) > 0:
                 p= subprocess.Popen(["ssh","-t","-t",Login+'@'+IP,command], stdout=subprocess.PIPE)
                 output,err= p.communicate()
    elif re.search('.*:.*:.*:.*:.*:.*:.*:.*',IP):
         if int(os.popen('ping6 -c 2 %s|grep received | cut -d, -f2 |grep -o [0-9]'%IP).read().rstrip()) > 0:
                
                 p= subprocess.Popen(["ssh","-6","-t",Login+'@'+IP,command], stdout=subprocess.PIPE)
                 output,err= p.communicate()
    return output,err
def timeout_command(command, timeout):
    #"""call shell-command and either return its output or kill it
    #if it doesn't normally exit within timeout seconds and return None"""

    start = datetime.datetime.now()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while process.poll() is None:
      time.sleep(0.1)
      now = datetime.datetime.now()
      if (now - start).seconds> timeout:
        os.kill(process.pid, signal.SIGKILL)
        os.waitpid(-1, os.WNOHANG)
        return None
    return process.stdout.read()
    
def IS_csv_data_processing (IS_data,IS_col):
   data=copy.deepcopy(IS_data)

   for i in sorted(data):
    
        #### Replacing \n in table_drops
         table_drops=data[i][IS_col.index('Table_Drops (Yesterday to Current)')]
         data[i][IS_col.index('Table_Drops (Yesterday to Current)') ]= table_drops.replace(",   \n",";")
#  
#    
   return data   

def IS_data_collection (is_output,link_data,IS_col):
 ##is_output is original dictionary based on IP Keys
##'10.193.86.33': {'data_13': [1.3779999999999999, 1136.3299999999999, '2017-01-10 17:00:00-05', 756.70000000000005, '0', '2017-01-09 22:00:00-05', 34.450000000000003], 
##'data_12': [0.0, 0.070000000000000007, '2017-01-10 20:00:00-05', 0.070000000000000007, '0', '2017-01-09 22:00:00-05', 'null'], 'IF': ['12', '13']}  
## data_if:[ 24 hr Link Util Gbps, 24 hr peak pps (K), PPS time,Last hr peak pps (K),dropped packets, dropped packet time, active streams]
   
    ###IS_STATS
  ## Soft versions , Models,ASI_Mode, Total HDD,Total ESUs, Total Packet storage ,Total Interfaces
  ###IS_Error
  ### IS_error_summary: Total interfaces dropping tables, Total interfaces dropping packets
     soft_ver={}
     Model={}
     Asi_mode={}
     Total_HDD=0
     Total_ESUs=0
     Total_Pkt_Storage=0
     Total_Interfaces=0
     Total_Failed_HDD=0
     Total_voice=0
     Total_If_pkt_drops=0
     Total_If_table_drops=0
     Total_If_interfaces={}
     Total_If_voice=0
     Total_If_notraffic=0
     Total_If_low_s1nas=0
     Total_If_asr_tbldrops=0
     Total_If_asi_tbldrops=0
     Total_If_cdm_tbldrops=0
     Total_If_other_tbldrops=0
     IS_If_Drops={}
     IS_If_notraffic_lasthr={}
     IS_data_retention={}
     IS_If_vifn_mode={}

#### IS Summary   
       
     for ip,i in is_output.items():   
     ####Soft Versions
         if i[IS_col.index('Version')] not in soft_ver:
            #soft_ver.append(i[IS_col.index('Version')])
            soft_ver[i[IS_col.index('Version')]]=1
         elif i[IS_col.index('Version')] in soft_ver:
            soft_ver[i[IS_col.index('Version')]]+=1
             
     ###Model Versions
         if (i[IS_col.index('Model')] not in Model) and (i[IS_col.index('Model')] != 'NA'):
             Model.update({i[IS_col.index('Model')]:1})
         elif i[IS_col.index('Model')] in Model:
             Model[i[IS_col.index('Model')]]+=1
     ### Asi_mode
         if (i[IS_col.index('Asi_mode')] not in Asi_mode) and (i[IS_col.index('Asi_mode')] != 'NA'):
             Asi_mode.update({i[IS_col.index('Asi_mode')]:1})
         elif i[IS_col.index('Asi_mode')]  in Asi_mode:
             Asi_mode[i[IS_col.index('Asi_mode')]]+=1  
     ### Total HDD 
         Total_HDD=Total_HDD+int(i[IS_col.index('HDD')])      
     ### Total ESUs
         Total_ESUs=Total_ESUs+int(i[IS_col.index('ESUs')])
     ### Total Packet Storage
         if i[IS_col.index('Packet Store Size(GB)')]:
            Total_Pkt_Storage=Total_Pkt_Storage+float(i[IS_col.index('Packet Store Size(GB)')])
     #### 'Voice Monitoring'
         if re.search('on',i[IS_col.index('Voice Monitoring')]):
             Total_voice+=1
     ### Total Failed HDD
         Total_Failed_HDD=Total_Failed_HDD+int(i[IS_col.index('Failed HDD')]) 
     ### Data retention with less than a day
         if re.search('^(?![1-9].*day(?:s)?)',i[IS_col.index('Packet Data Retention')]):
              IS_data_retention[is_output[ip][0]]=i[IS_col.index('Packet Data Retention')]
         

     #### Interface  Summary
         if ip in link_data:
              Total_Interfaces=Total_Interfaces+len(link_data[ip]['IF'])
              for IF in link_data[ip]['IF']:
                    if  link_data[ip]['data_'+IF][4] != '0':
                         Total_If_pkt_drops=Total_If_pkt_drops+1
                         if i[IS_col.index('Hostname')] not in IS_If_Drops:
                             IS_If_Drops.update({i[IS_col.index('Hostname')]:['If-%s'%IF]})
                         elif i[IS_col.index('Hostname')] in IS_If_Drops:
                             IS_If_Drops[i[IS_col.index('Hostname')]].append('If-%s'%IF)
                    if re.search('(%s:.*[a-zA-Z]):.*:.*'%IF,i[IS_col.index('Table_Drops (Yesterday to Current)')]):
                         Total_If_table_drops=Total_If_table_drops+1
                    Interface_type=re.findall('if_%s:(.*)'%IF,i[IS_col.index('Interface_Type')])
                    if Interface_type:
                       if Interface_type[0] not in Total_If_interfaces:
                             Total_If_interfaces.update({Interface_type[0]:1})
                       elif Interface_type[0]  in Total_If_interfaces:
                             Total_If_interfaces[Interface_type[0]]+=1
                    Vifn=re.findall('if_%s:(.*)'%IF,i[IS_col.index('Vifn_mode')])
                    if Vifn:
                       if Vifn[0] not in IS_If_vifn_mode:
                             IS_If_vifn_mode[Vifn[0]]=1
                       elif Vifn[0]  in IS_If_vifn_mode:
                             IS_If_vifn_mode[Vifn[0]]+=1
 
                    if re.search('[0-9]',str(link_data[ip]['data_'+IF][6])):
                          Total_If_voice+=1
                    if link_data[ip]['data_'+IF][1]==0.000:
                          Total_If_notraffic+=1
                    if S1MME:
                       if_nas=re.findall('if_%s:([0-9].*)\''%IF,i[IS_col.index('NAS_Deciphering rate %')])
                       if if_nas:
                           nas_value=float(if_nas[0])
                           if nas_value <80.0:
                               Total_If_low_s1nas+=1
                    if re.search('%s:asr_'%IF,i[IS_col.index('Table_Drops (Yesterday to Current)')]):
                            Total_If_asr_tbldrops+=1
                    if re.search('%s:asi_'%IF,i[IS_col.index('Table_Drops (Yesterday to Current)')]):
                           Total_If_asi_tbldrops+=1
                    if re.search('%s:cdm_'%IF,i[IS_col.index('Table_Drops (Yesterday to Current)')]):
                           Total_If_cdm_tbldrops+=1
                    if re.search('%s:ses_|%s:skt_'%(IF,IF),i[IS_col.index('Table_Drops (Yesterday to Current)')]):
                           Total_If_other_tbldrops+=1
                           
                    if link_data[ip]['data_'+IF][1] > 0.000 and link_data[ip]['data_'+IF][3]==0.000:
                         if i[IS_col.index('Hostname')] not in IS_If_notraffic_lasthr:
                             IS_If_notraffic_lasthr.update({i[IS_col.index('Hostname')]:['If-%s'%IF]})
                         elif i[IS_col.index('Hostname')] in IS_If_Drops:
                             IS_If_notraffic_lasthr[i[IS_col.index('Hostname')]].append('If-%s'%IF)
     #
                 
     return {
         
              'Soft_ver':soft_ver,
              'IS_model':Model,
              'Asi_mode':Asi_mode,
              'Total_HDD':Total_HDD,
              'Total_ESUs':Total_ESUs,
              'Total_Pkt_Storage':Total_Pkt_Storage,
              'Total_voice':Total_voice,
              'Total_Interfaces':Total_Interfaces,
              'IS_data_retention':IS_data_retention,
              'Total_If_pkt_drops':Total_If_pkt_drops,
              'Total_If_table_drops':Total_If_table_drops,
              'Failed_HDD': Total_Failed_HDD,
              'Total_If_interfaces':Total_If_interfaces,
              'Total_If_voice':Total_If_voice,
              'Total_If_notraffic':Total_If_notraffic,
              'Total_If_low_s1nas':Total_If_low_s1nas,
              'Total_If_asr_tbldrops':Total_If_asr_tbldrops,
              'Total_If_asi_tbldrops':Total_If_asi_tbldrops,
              'Total_If_cdm_tbldrops':Total_If_cdm_tbldrops,
              'Total_If_other_tbldrops':Total_If_other_tbldrops,
              'IS_If_Drops':IS_If_Drops,
              'IS_If_vifn_mode':IS_If_vifn_mode,
              'IS_If_notraffic_lasthr':IS_If_notraffic_lasthr
              }
              
              
                                             
           
             
def PM_data_collection (pm_output, pm_input_list,PM_col):
#    ### PMstats
#    ### Soft versions, Total storage (/opt), 
#    ### PM Error Summary
     PM_type={}
     PM_soft_ver=[]
     ASI_load={}
     PM_HDD=0
     Total_local_storage=0
     
     for i in pm_input_list:
        pm_type=i.split(",")
        if pm_type[1] not in PM_type:
            PM_type.update({pm_type[1]:1})
        else:
            PM_type[pm_type[1]]+=1
     for j in pm_output.values():
         ####Soft Versions
         if j[PM_col.index('Software version')] not in PM_soft_ver:
            PM_soft_ver.append(j[PM_col.index('Software version')])
         
         ### ASI_load 
         peak_load=0
         if (j[PM_col.index('Hostname')] not in ASI_load) and  re.search('[0-9]',j[PM_col.index('Peak ASI Rows')]):
            if j[PM_col.index('Peak ASI Rows')] !='N/A' and (int(j[PM_col.index('Peak ASI Rows')]) > 10000000):
                  peak_load=j[PM_col.index('Peak ASI Rows')]
                  ASI_load.update ({j[PM_col.index('Hostname')]: peak_load})
             
         ### Total Storage
         if re.search('Local',j[PM_col.index('PM_Type')]):
              try:
                Total_local_storage+=float(j[PM_col.index('Disk_Size(/opt)')])
              except:
                 Total_local_storage='NA'
              
         ### PM HDD
                  ### Total Storage
         if re.search('[0-9]',j[PM_col.index('HDD')]):
              PM_HDD+=int(j[PM_col.index('HDD')])
         
     return {
        'PM_Type':PM_type,
        'PM_soft_ver':PM_soft_ver,
        'ASI_load':ASI_load,
        'PM_HDD':PM_HDD,
        'Local_PM_storage':Total_local_storage
        
        }
def email_html(IS_collec,IS_err_summ, PM_collec, PM_err_summ,ln_status):

    html = """
       <html>
       <head></head>
       <style>
           h5 {
         color:lightgrey;
         font-size:75%%
        
         }
         h4 {
         font-family:"Bradley Hand ITC";
         color:red
         }
         h3{
         font-family:"Bradley Hand ITC";
         color:brown
         }
          div{
         font-family:sans-serif;
         font-size:85%%
         }
         </style>
          <body>
          <h5>Health-Check Script Version:%s<br>%s<br></h5>
          <h1><font face="Bradley Hand ITC" ><u>%s Health-Check Summary</u></font></h1> 
        <p>
           <h3>nGONE</h3>  
           <div>Total PM targeted : %s</div>\n """%(Version,ctime(),Deployment, PM_t)
    if Ping_Disable is False:
       html+="""<div>Count of PMs not responding to Ping : %s</div>\n """%(PM_u)
    
    ###color="blue"   h3-->  color:blue
    ### PM Stats###########################################################
    ### <div></div>
    html+="<div>PM types: "
    html_v=''
    for j,k in PM_collec['PM_Type'].items():
        
           html_v+=" %s : %s, "%(j,k)
    html+=html_v[:-2]+'</div>\n'
    
    ### PM_Soft Ver
    ### <div></div>
    html+="<div>PM software versions: "
    html_v=''
    for i in PM_collec['PM_soft_ver']:
        
           html_v+=" %s, "%(i)
    html+=html_v[:-2]+'</div>\n'
    
    ### ASI_load 
    ### <div></div>
    if PM_collec['ASI_load']:
       html+="<div>Peak  ASI load greater than 10 mil:</div>\n  "
       html_v=''
       if PM_collec['ASI_load']:
          for j,k in PM_collec['ASI_load'].items():
              
                 html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n  "%(j,k)
       html+=html_v
    
    ### PM HDD
    html+=" <div>Total PM HDDs: %s </div>\n " %PM_collec['PM_HDD']
    ### Total_Storage 
    html+=" <div>Total storage (/opt) on local PMs(TB): %s </div>\n " %PM_collec['Local_PM_storage']
    
    html+="</p>"
    #############################################################################      
    
    
    ### Infinistream stats
    
    
    
    ##
    ##  
       ##       'Soft_ver':soft_ver,
       ##       'IS_model':Model,
       ##       'Asi_mode':Asi_mode,
       ##       'Total_HDD':Total_HDD,
       ##       'Total_ESUs':Total_ESUs,
       ##       'Total_Pkt_Storage':Total_Pkt_Storage,
       ##       'Total_voice':Total_voice,
       ##       'Total_Interfaces':Total_Interfaces,
       ##       'Total_If_pkt_drops':Total_If_pkt_drops,
       ##       'Total_If_table_drops':Total_If_table_drops,
       ##       'Failed_HDD': Total_Failed_HDD,
       ##       'Total_If_interfaces':Total_If_interfaces,
       ##       'Total_If_voice':Total_If_voice,
       ##       'Total_If_notraffic':Total_If_notraffic,
       ##       'Total_If_low_s1nas':Total_If_low_s1nas,
       ##       'Total_If_asr_tbldrops':Total_If_asr_tbldrops,
       ##       'Total_If_asi_tbldrops':Total_If_asi_tbldrops,
       ##       'Total_If_cdm_tbldrops':Total_If_asi_tbldrops,
       ##       'Total_If_other_tbldrops':Total_If_other_tbldrops
       ##       'IS_If_Drops':IS_If_Drops{}
       ##        'IS_If_notraffic_lasthr':IS_If_notraffic_lasthr{}
    
    html+= "<p><h3>Infinistream</h3>"
    html+=""" 
           <div>Total IS targeted : %s</div>"""%IS_t
           
    if Ping_Disable is False:      
      html+="""<div>Count of IS not responding to Ping : %s</div>\n """%IS_u
           
    ### Software Version
    if IS_collec['Soft_ver']:
        html+="<div>IS software versions: </div> "
        html_v=''
        for j,k in IS_collec['Soft_ver'].items():
            
               #html_v+=" %s, "%(i.replace('CDM',''))
            html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n  "%(j.replace('CDM',''),k)   
        html+=html_v
    
    ### IS Model 
    ### <div></div>
    if IS_collec['IS_model']:
       html+="<div>IS models:</div>\n  "
       html_v=''
       for j,k in IS_collec['IS_model'].items():
           if re.search('[A-Za-z]|[0-9]',j): ### to avoid blank entries
              html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n  "%(j,k)
    html+=html_v
    ### Asi_mode 
    ### <div></div>
    if IS_collec['Asi_mode']:
        html+="<div>IS ASI modes:</div>\n  "
        html_v=''
        for j,k  in IS_collec['Asi_mode'].items():
           if re.search('[A-Za-z]|[0-9]',j): 
               html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n "%(j,k)      
    html+=html_v
    if Voice_IS:
     ### Total IS with Voice/Video Monitoring
     html+=" <div>Total IS with Voice/Video Monitoring: %s </div>\n " %IS_collec['Total_voice'] 
    
    ### Total HDD
    html+=" <div>Total IS HDDs: %s </div>\n " %IS_collec['Total_HDD']   
    
    ### Total ESUs
    html+=" <div>Total IS ESUs: %s </div>\n " %IS_collec['Total_ESUs'] 
    
    ### Total Packet Storage
    html+=" <div>Total IS packet storage(TB): %s </div>\n " %(round(IS_collec['Total_Pkt_Storage']*0.001,2)) 
    html+="</p>"

    #### Data retention####
    if IS_collec['IS_data_retention']:
        html+="<div>IS with Packet data retention less than 24hr :</div>\n  "
        html_v=''
        for j,k  in IS_collec['IS_data_retention'].items():
           if re.search('[A-Za-z]|[0-9]',j): 
               html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n "%(j,k)
        html+=html_v
    ###################################################################################
    
    ###Interface Stats##################
    if ln_status == 'Yes' or ln_status =='yes':
         html+="<h3>Interface Stats</h3>"
         html+="""<div><i>**Please refer to IS_Interface_Stats.html for details</i></div>\n """
         html+="""<div>&nbsp;</div>\n """
         html+="<p>"
         ### Total Interfaces
         if IS_collec['Total_Interfaces']:
          html+=" <div>Total IS interfaces: %s </div>\n " %IS_collec['Total_Interfaces']  
         
         #### IS Interface
         if IS_collec['Total_If_interfaces']:
            html+="<div>IS interface types:</div>\n"
            html_v=''
            for j,k  in IS_collec['Total_If_interfaces'].items():
                
                   html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n "%(j,k)      
            html+=html_v  
         #### IS Vifn_mode
         if IS_collec['IS_If_vifn_mode']:
            html+="<div>IS vifn_mode:</div>\n"
            html_v=''
            for j,k  in IS_collec['IS_If_vifn_mode'].items():
                
                   html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n "%(j,k)      
            html+=html_v  
        
         ### Total Interface with no traffic
         
         html+=" <div>Total IS interfaces with No traffic (last 24 hrs): %s</div>\n" %IS_collec['Total_If_notraffic']
         ### Interfaces with no traffic last hour

         if IS_collec['IS_If_notraffic_lasthr'] :
                   
            html+=" <div>IS and Interfaces with No traffic in last hr (only interfaces with peak PPS > 0 in last 24 hr): </div>\n"
            html_v=''
            for j,k  in sorted(IS_collec['IS_If_notraffic_lasthr'].items()):
                
                   html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n "%(j,str(k).strip('[]').replace('\'',''))     
            html+=html_v         
         ### Voice Traffic    
         if Voice_IS:
           html+=" <div>Total IS interfaces with UC(voice/video) traffic: %s </div>\n" %IS_collec['Total_If_voice']
          ### Total Interfaces Packet drops
         if IS_collec['Total_If_pkt_drops'] :
            html+=" <div>Total IS interfaces Dropping packets (last 24 hrs): %s </div>\n" %IS_collec['Total_If_pkt_drops']       
            html+=" <div>IS and Interfaces Dropping packets (last 24 hrs): </div>\n"
            html_v=''
            for j,k  in sorted(IS_collec['IS_If_Drops'].items()):
                
                   html_v+="<div>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s : %s</div>\n "%(j,str(k).strip('[]').replace('\'',''))     
            html+=html_v           
          ### Total Interfaces table drops
         html+=" <div>Total IS interfaces Dropping tables (yest to curr): %s </div>\n" %IS_collec['Total_If_table_drops'] 
         
         ### Total ASI table drops
         if IS_collec['Total_If_table_drops']:
            html+=" <div>Total IS interfaces Dropping ASI tables (yest to curr): %s </div>\n" %IS_collec['Total_If_asi_tbldrops'] 
         ### Total ASR table drops
         if IS_collec['Total_If_table_drops']:
           html+=" <div>Total IS interfaces Dropping ASR tables (yest to curr): %s </div>\n" %IS_collec['Total_If_asr_tbldrops'] 
         ### Total CDM table drops
         if IS_collec['Total_If_cdm_tbldrops']:
           html+=" <div>Total IS interfaces Dropping CDM tables (yest to curr): %s </div>\n" %IS_collec['Total_If_cdm_tbldrops'] 
         ### Total other table drops
         if IS_collec['Total_If_table_drops']:
           html+=" <div>Total IS interfaces Dropping Other(ses,skt) tables (yest to curr): %s </div>\n" %IS_collec['Total_If_other_tbldrops'] 
         if S1MME:
            ### S1MME low NAS DECIPHERING
            html+=" <div>Total S1 interfaces with low NAS deciphering (<80%%):%s</div>\n" %IS_collec['Total_If_low_s1nas']
    
         html+="</p>"
    
    ############################################################
     ##### Error Summary
    html+="<h3>Errors</h3>"
    html+="<div><i>**Please refer to Error_Summary.html for details</i></div>\n"
    html+="<p>" 
    if PM_l or PM_s or PM_err_summ:    
      html+="<h4>PM Errors</h4>"
   
       ### Ping not responding list of PM
      if PM_l:
        html+="""<div>PMs not responding to ping ="""  
        html_v=''      
        for i in PM_l:
             html_v+='%s, '%i
        html+=html_v[:-1]+'</div>\n'
        ### SSH not responding list of SSH
      if PM_s:
        html+="""<div>PMs not responding to SSH ="""
        html_v=''
        for i in PM_s:
             html_v+='%s, '%i
        html+=html_v[:-2]+'</div>\n\n' 
      html_v=''
      for i in PM_err_summ:
        
            if PM_err_summ[i]:
              html_v+="<div> %s: %s</div>\n"%(i,len(PM_err_summ[i]))
             
      html+=html_v
    #----------------------------------------------------------------------------
    if IS_l or IS_s or IS_err_summ:    
      html+="<h4>Infinistream Errors</h4>"
      html+="""<div><i>**Please refer to /opt/platform/nshwmon/log/nshwmon-logfiles in IS for HW failures </i></div>\n """
      html+="""<div>&nbsp;</div>\n """
       ### Ping not responding list of IS
      if IS_l:
        html+="""<div>IS not responding to ping ="""
        html_v=''
        for i in IS_l:
             html_v+='%s, '%i
        html+=html_v[:-1]+'</div>\n'
        ### SSH not responding list of SSH
      if IS_s:
        html+="""<div>IS not responding to SSH ="""
        html_v=''
        for i in IS_s:
             html+='%s, '%i
        html+=html_v[:-2]+'</div>\n' 
      html_v=''
      for i in IS_err_summ:
         
             if IS_err_summ[i]:
               if re.search('HDD Failed',i):
                 html_v+="<div> %s: %s</div>\n"%(i,len(IS_err_summ[i]))
                 html_v+="<div> Total Failed Disk(HDD)     : %s</div>\n"%IS_collec['Failed_HDD']
                         
               else:
                   html_v+="<div> %s: %s</div>\n"%(i,len(IS_err_summ[i]))
        
      html+=html_v
       
    html+=" </p></body>"
    return html    
 
def get_s1_interfaces(is_output,IS_col):
    S1_ip={}
    for ip in is_output:
             s1=is_output[ip][IS_col.index('Interface_Type')]    

             if re.findall('.*S1.*',s1):
                for i in re.findall('.*S1.*',s1):
                      i=i.rstrip()
                      if re.search('S1$',i):
                         Interface=re.findall('if_(.*):.*',i)
                         if ip not in S1_ip:
                            S1_ip.update({ip:[Interface[0]]})
                         else:
                            S1_ip[ip].append (Interface[0])
    return S1_ip
    
def s1_nas_deciphering(is_output,IS_col):
     S1_output={}
     S1_ip=get_s1_interfaces(is_output,IS_col)
     if S1_ip:
         for ip in S1_ip:
           S1_output.update({ip:[]})
           for inf in S1_ip[ip]:
              command="""pkill -9 localconsole;echo if_%s|tr '\\n' ':';echo -e "11\\nget dump nas_msg %s perf\\nexit\\n"| sudo /opt/NetScout/rtm/bin/localconsole|grep "01.*(%%)"|head -1|awk '{print $2}'|sed -n 's/\\(.*[0-9]\\).*/\\1/p' """%(inf,inf)
              output,err=ssh_command(ip,command)
              if output:
                S1_output[ip].append(output.rstrip())
     #### appending in the original is_output           
     for ip in is_output:
       if ip in S1_output:
             is_output[ip].append(str(S1_output[ip]).strip('[]').replace(',','\n'))
       else:
             is_output[ip].append("NA")
             
def is_output_post_processing(is_output,IS_col):
  localconsole_metric=['Model','Version','Asi_mode','Serial Number','PM Server','Nsprobe Mem','Free_Mem','Table_Size_Allocation(ifn-size-ctrl-data)','nsprobe uptime',
  'Table_Drops (Yesterday to Current)','Interface_Type']

  for ip in is_output:
           #### Delete the count 1 on ESUs if its greater than 0
           if int(is_output[ip][IS_col.index('ESUs')]) >0:
                is_output[ip][IS_col.index('ESUs')]=int(is_output[ip][IS_col.index('ESUs')])-1 
           
           ### Insert NA on missing data
           if  int(is_output[ip][IS_col.index('HDD')])== 0 and re.search ('^\s*$', is_output[ip][IS_col.index('FAN Status')]):
               is_output[ip][IS_col.index('FAN Status')]='NA'
               is_output[ip][IS_col.index('POWER Status')]='NA'
               is_output[ip][IS_col.index('Temperature Status')]='NA'
               is_output[ip][IS_col.index('Voltage Status')]='NA'
           if  re.search ('^\s*$', is_output[ip][IS_col.index('Model')]) and re.search ('^\s*$', is_output[ip][IS_col.index('Free_Mem')]):
               for i in localconsole_metric:
                    is_output[ip][IS_col.index('%s'%i)]='NA'
           ############# Data Rentention#########
           try:
                print_store = is_output[ip][IS_col.index('Packet Data Retention')]
                start_time  = re.findall('mStartTime\s*= ([0-9]*)',print_store)[0]
                end_time    = re.findall('mEndTime\s*= ([0-9]*)',print_store)[0]
                delta       = datetime.datetime.fromtimestamp(float(end_time))- datetime.datetime.fromtimestamp(float(start_time))
                is_output[ip][IS_col.index('Packet Data Retention')] = str(delta)
           except:     
                is_output[ip][IS_col.index('Packet Data Retention')] = '0 days'

           ########### ns probe uptime
           try:
                is_output[ip][IS_col.index('nsprobe uptime')]= re.findall('.*>(.*)',is_output[ip][IS_col.index('nsprobe uptime')])[0].rstrip()
           except:
                is_output[ip][IS_col.index('nsprobe uptime')]='NA'

def pm_output_post_processing(pm_output,PM_col): 
  for ip in pm_output:          
    if  re.search('St.*by',  pm_output[ip][PM_col.index('PM_Type')]):
         pm_output[ip][PM_col.index('Config_Backup Last Date')]='NA' 
         
    
if __name__ == "__main__":
   main(sys.argv[1:])




