__author__ = 'Amal G Jose'

import time
import logging
from boto.emr.connection import EmrConnection
from boto.emr.bootstrap_action import BootstrapAction
from boto.emr.step import InstallHiveStep
from boto.emr.step import InstallPigStep
from boto.regioninfo import RegionInfo


class EmrLauncher(object):

    # Default constructor of the class.
    def __init__(self):
        try:
            self.zone_name = "ap-southeast-1"
            self.access_key = "xxxxxx"
            self.private_key = "xxxxxxx"
            self.ec2_keyname = "xxxxxxxx"
            self.base_bucket = "s3://emr-bucket/"
            self.bootstrap_script = "custom-bootstrap.sh"
            self.log_dir = "Logs"
            self.emr_status_wait = 20
            self.conn = ""
            self.cluster_name = "MyFirstEmrCluster"

            # Establishing EmrConnection
            self.conn = EmrConnection(self.access_key, self.private_key,
                                 region=RegionInfo(name=self.zone_name,
                                 endpoint=self.zone_name + '.elasticmapreduce.amazonaws.com'))


            self.log_bucket_name = self.base_bucket + self.log_dir
            self.bootstrap_script_name = self.base_bucket + self.bootstrap_script

    def launch_emr_cluster(self, master_type, slave_type, num_instance, ami_version):
        try:
            #Custom Bootstrap step
            bootstrap_step = BootstrapAction("CustomBootStrap", self.bootstrap_script_name, None)

            #Modifyting block size to 256 MB
            block_size_conf = 'dfs.block.size=256'
            hadoop_config_params = ['-h', block_size_conf, '-h']
            hadoop_config_bootstrapper = BootstrapAction('hadoop-config',
                                               's3://elasticmapreduce/bootstrap-actions/configure-hadoop',
                                               hadoop_config_params)
            #Bootstrapping Ganglia
            hadoop_monitor_bootstrapper = BootstrapAction('ganglia-config',
                                                's3://elasticmapreduce/bootstrap-actions/install-ganglia', '')

            #Bootstrapping Impala
            impala_install_params = ['--install-impala','--base-path', 's3://elasticmapreduce', '--impala-version', 'latest']
            bootstrap_impala_install_step = BootstrapAction("ImpalaInstall", "s3://elasticmapreduce/libs/impala/setup-impala",
                                                                                                impala_install_params)
            #Hive installation
            hive_install_step = InstallHiveStep();

            #Pig Installation
            pig_install_step = InstallPigStep();

            #Launching the cluster
            jobid = self.conn.run_jobflow(
                         self.cluster_name,
                         self.log_bucket_name,
                         bootstrap_actions=[hadoop_config_bootstrapper, hadoop_monitor_bootstrapper, bootstrap_step,
                                            bootstrap_impala_install_step],
                         ec2_keyname=self.ec2_keyname,
                         steps=[hive_install_step, pig_install_step],
                         keep_alive=True,
                         action_on_failure = 'CANCEL_AND_WAIT',
                         master_instance_type=master_type,
                         slave_instance_type=slave_type,
                         num_instances=num_instance,
                         ami_version=ami_version)

            #Enabling the termination protection
            self.conn.set_termination_protection(jobid, True)

            #Checking the state of EMR cluster
            state = self.conn.describe_jobflow(jobid).state
            while state != u'COMPLETED' and state != u'SHUTTING_DOWN' and state != u'FAILED' and state != u'WAITING':
                #sleeping to recheck for status.
                time.sleep(int(self.emr_status_wait))
                state = self.conn.describe_jobflow(jobid).state

            if state == u'SHUTTING_DOWN' or state == u'FAILED':
                logging.error("Launching EMR cluster failed")
                return "ERROR"

            #Check if the state is WAITING. Then launch the next steps
            if state == u'WAITING':
                #Finding the master node dns of EMR cluster
                master_dns = self.conn.describe_jobflow(jobid).masterpublicdnsname
                logging.info("Launched EMR Cluster Successfully")
                logging.info("Master node DNS of EMR " + master_dns)
                return "SUCCESS"
        except:
            logging.error("Launching EMR cluster failed")
            return "FAILED"

    def main(self):
        try:
            master_type = 'm3.xlarge'
            slave_type = 'm3.xlarge'
            num_instance = 3
            ami_version = '2.4.8'

            emr_status = self.launch_emr_cluster(master_type, slave_type, num_instance, ami_version)
            if emr_status == 'SUCCESS':
                logging.info("Emr cluster launched successfully")
            else:
                logging.error("Emr launching failed")
        except:
            logging.error("Emr launching failed")


if __name__ == '__main__':

    launcher = EmrLauncher()
    launcher.main()

