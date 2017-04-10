#TODO: WebUI wrap

class WebUIWrap:

   ''' Wrapper class for Contrail Web UI

       Provides create, update, delete methods for contrail resources.
       Methods create & update, expect the resource desc (kwargs) to be
       consistent with contrail-schema (i.e, as per contrailv2 heat templates)
   '''

   def is_supported_type (self, args):
       return arg in ['ContrailV2']

   #TODO def create_service_template (self, **kwargs):
   #TODO def delete_service_template (self, **kwargs):
   #TODO def update_service_template (self, **kwargs):
