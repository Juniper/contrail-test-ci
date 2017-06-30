from time import sleep

from common.servicechain.config import ConfigSvcChain
from tcutils.commands import ssh, execute_cmd, execute_cmd_out
from common.ecmp.ecmp_traffic import ECMPTraffic
from common.ecmp.ecmp_verify import ECMPVerify


class ConfigSvcMirror(ConfigSvcChain):

    def start_tcpdump(self, session, tap_intf, vm_fixtures=[], pcap_on_vm=False, vlan=None):
        pcap = '/tmp/mirror-%s.pcap' % tap_intf
        cmd = 'rm -f %s' % pcap
        execute_cmd(session, cmd, self.logger)
        sleep(5)
        filt_str = ''
        if not vlan:
            filt_str = 'udp port 8099'
        cmd = "tcpdump -ni %s %s -w %s" % (tap_intf, filt_str, pcap)
        self.logger.info("Staring tcpdump to capture the mirrored packets.")
        execute_cmd(session, cmd, self.logger)
        return pcap

    def stop_tcpdump(self, session, pcap, filt=''):
        self.logger.info("Waiting for the tcpdump write to complete.")
        sleep(30)
        cmd = 'kill $(pidof tcpdump)'
        execute_cmd(session, cmd, self.logger)
        execute_cmd(session, 'sync', self.logger)
        cmd = 'tcpdump -r %s %s | wc -l' % (pcap, filt)
        out, err = execute_cmd_out(session, cmd, self.logger)
        count = int(out.strip('\n'))
        cmd = 'rm -f %s' % pcap
        execute_cmd(session, cmd, self.logger)
        return count

    def tcpdump_on_all_analyzer(self, si_fixtures, si_prefix, si_count=1):
        sessions = {}
        for i in range(0, si_count):
            si_fixture = si_fixtures[i]
            svms = self.get_svms_in_si(si_fixture, self.inputs.project_name)
        for svm in svms:
            svm_name = svm.name
            host = self.get_svm_compute(svm_name)
            tapintf = self.get_svm_tapintf(svm_name)
            session = ssh(host['host_ip'], host['username'], host['password'])
            pcap = self.start_tcpdump(session, tapintf)
            sessions.update({svm_name: (session, pcap)})

        return sessions
