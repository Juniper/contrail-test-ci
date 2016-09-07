'''
Contrail feature specific utility methods
'''


def get_ri_name(vn_fq_name):
    '''
    Return RI name given a VN fq name
    vn_fq_name can be a list or a string(colon separated)
    '''
    if type(vn_fq_name) == list:
        vn_name = vn_fq_name[-1]
        return vn_fq_name + vn_name
    else:
        vn_name = vn_fq_name.split(':')[-1]
        return vn_fq_name + ':' + vn_name
# end get_ri_name
