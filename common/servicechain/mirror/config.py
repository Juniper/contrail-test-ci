from time import sleep

from common.servicechain.config import ConfigSvcChain
from tcutils.commands import ssh, execute_cmd, execute_cmd_out
from common.ecmp.ecmp_traffic import ECMPTraffic
from common.ecmp.ecmp_verify import ECMPVerify
from tcutils.util import get_random_cidr, get_random_name


class ConfigSvcMirror(ConfigSvcChain):

    def start_tcpdump(self, session, tap_intf, vm_fixtures=[], pcap_on_vm=False):
        if not pcap_on_vm:
            pcap = '/tmp/mirror-%s.pcap' % tap_intf
            cmd = 'rm -f %s' % pcap
            execute_cmd(session, cmd, self.logger)
            sleep(5)
            cmd = "tcpdump -ni %s udp port 8099 -w %s" % (tap_intf, pcap)
            self.logger.info("Staring tcpdump to capture the mirrored packets.")
            execute_cmd(session, cmd, self.logger)
            return pcap
        else:
            pcap = '/tmp/%s.pcap' % (get_random_name())
            cmd_to_tcpdump = [ 'tcpdump -ni %s udp port 8099 -w %s 1>/dev/null 2>/dev/null' % (tap_intf, pcap) ]
            pidfile = pcap + '.pid'
            vm_fix_pcap_pid_files =[]
            for vm_fixture in vm_fixtures:
                vm_fixture.run_cmd_on_vm(cmds=cmd_to_tcpdump, as_daemon=True, pidfile=pidfile, as_sudo=True)
                vm_fix_pcap_pid_files.append((vm_fixture, pcap, pidfile))
            return vm_fix_pcap_pid_files

    def stop_tcpdump(self, session, pcap, filt='', vm_fix_pcap_pid_files=[], pcap_on_vm=False):
        self.logger.info("Waiting for the tcpdump write to complete.")
        sleep(30)
        if not pcap_on_vm:
            cmd = 'kill $(pidof tcpdump)'
            execute_cmd(session, cmd, self.logger)
            execute_cmd(session, 'sync', self.logger)
            cmd = 'tcpdump -r %s %s | wc -l' % (pcap, filt)
            out, err = execute_cmd_out(session, cmd, self.logger)
            count = int(out.strip('\n'))
            cmd = 'rm -f %s' % pcap
            execute_cmd(session, cmd, self.logger)
            return count
        else:
            output = []
            pkt_count = []
            for vm_fix, pcap, pidfile in vm_fix_pcap_pid_files:
                cmd_to_output  = 'tcpdump -nr %s %s' % (pcap, filt)
                cmd_to_kill = 'cat %s | xargs kill ' % (pidfile)
                count = cmd_to_output + '| wc -l'
                vm_fix.run_cmd_on_vm(cmds=[cmd_to_kill], as_sudo=True)
                vm_fix.run_cmd_on_vm(cmds=[cmd_to_output], as_sudo=True)
                output.append(vm_fix.return_output_cmd_dict[cmd_to_output])
                vm_fix.run_cmd_on_vm(cmds=[count], as_sudo=True)
                pkts = int(vm_fix.return_output_cmd_dict[count].split('\n')[2])
                pkt_count.append(pkts)
                total_pkts = sum(pkt_count)
            return output, total_pkts

    def tcpdump_on_all_analyzer(self, si_fixtures, si_prefix, si_count=1, pcap_on_vm=False, tap_intf='eth0'):
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

    def pcap_on_all_vms_and_verify_mirrored_traffic(
        self, src_vm_fix, dst_vm_fix, svm_fixtures, count, filt='', tap='eth0', expectation=True):
            vm_fix_pcap_pid_files = self.start_tcpdump(None, tap_intf=tap, vm_fixtures= svm_fixtures, pcap_on_vm=True)
            assert src_vm_fix.ping_with_certainty(
                dst_vm_fix.vm_ip, expectation=expectation)
            output, total_pkts = self.stop_tcpdump(
                None, pcap=tap, filt=filt, vm_fix_pcap_pid_files=vm_fix_pcap_pid_files, pcap_on_vm=True)
            if count > total_pkts:
                errmsg = "%s ICMP Packets mirrored to the analyzer VM,"\
                    "Expected %s packets, tcpdump on VM" % (
                     total_pkts, count)
                self.logger.error(errmsg)
                assert False, errmsg
            else:
                self.logger.info("Mirroring verified using tcpdump on the VM, Expected = Mirrored = %s " % (total_pkts))
            return True
    # end pcap_on_all_vms_and_verify_mirrored_traffic
