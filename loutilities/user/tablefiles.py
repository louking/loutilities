'''
filetables - support files endpoints
==============================================================
'''
# standard
from os.path import join, exists
from os import mkdir
from os import remove
from uuid import uuid4

# pypi
from flask import g, current_app, request
from loutilities.user.model import Column, String, Interest
from sqlalchemy.ext.declarative import declared_attr

# home grown
from .tables import DbCrudApiInterestsRolePermissions
from ..tables import CrudFiles
from loutilities.user.model import db

class ParameterError(Exception): pass

debug = False

class FieldUpload(CrudFiles):

    def __init__(self, **kwargs):
        '''
        upload endpoint for file uploads

        additional parameters

        :param filesdirectory: function which returns main folder in which files are to be stored.
                Subdirectories are maintained by interest. Must be a function as this needs to be in app context
        :param localinterestmodel: local model which holds interest entries
        :param filesmodel: local model which holds files entries based on FilesMixin
        :param fieldname: name of field in table/edit form which receives file id, may be callable
        '''
        # the args dict has default values for arguments added by this derived class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(
                    filesdirectory=None,
                    localinterestmodel=None,
                    filesmodel=None,
                    fieldname=None,
                    )
        args.update(kwargs)

        # this initialization needs to be done before checking any self.xxx attributes
        super().__init__(**args)

        # Caller must use some parameters
        if not callable(self.filesdirectory):
            raise ParameterError('filesdirectory required, and must be function')
        if not self.localinterestmodel and not self.filesmodel:
            raise ParameterError('localinterestmodel and filesmodel required')

    def upload(self):
        '''
        process post for file upload

        :return: {
            'upload' : {'id': fid },
            'files' : {
                'data' : {
                    fid : {'filename': thisfile.filename}
                },
            },

            NOTE: 'field': fid needs to be added by class which inherits this class
        '''
        if (debug): print('FilesUpload.upload()')

        # save gpx file
        thisfile = request.files['upload']
        fid, filepath = self.create_fidfile(g.interest, thisfile.filename, thisfile.mimetype)
        thisfile.save(filepath)
        thisfile.seek(0)

        # process file data; update route with calculated values
        # 'field': fid needs to be added by class which inherits this class

        returndata = {
            'upload' : {'id': fid },
            'files' : {
                'data' : {
                    fid : {'filename': thisfile.filename}
                },
            },
        }
        if self.fieldname:
            if callable(self.fieldname):
                returndata[self.fieldname()] = fid
            else:
                returndata[self.self.fieldname] = fid

        return returndata

    def list(self):

        if (debug): print('RunningRoutesFiles.list()')

        # list files whose parent is datafolderid
        table = 'data'
        filelist = {table:{}}
        files = self.filesmodel.query.all()
        for file in files:
            filelist[table][file.fileid] = {'filename': file.filename}

        return filelist

    def create_fidfile(self, group, filename, mimetype, fid=None):
        '''
        create directory structure for file group
        create a file in the database which has a fileid
        determine pathname for file

        NOTE: while directory structure is created here and filepath is determined, caller must save file

        :param group: files are grouped by "group", to allow separate permissions for separate groups
        :param filename: name of file
        :param mimetype: mimetype for file
        :param fid: optional file id, only used for initial data load
        :return: fid, filepath
        '''

        # make folder(s) if not there already
        mainfolder = self.filesdirectory()
        if not exists(mainfolder):
            # ug+rwx
            # note not getting g+w, https://github.com/louking/runningroutes/issues/63
            mkdir(mainfolder, mode=0o770)
        groupfolder = join(mainfolder, group)
        if not exists(groupfolder):
            mkdir(groupfolder, mode=0o770)

        # create file and save it's record; uuid4 gives unique fileid
        filename = filename
        # fid might be specified by caller -- this is only for external data loading
        if not fid:
            fid = uuid4().hex
        filepath = join(groupfolder, fid)
        interest = Interest.query.filter_by(interest=group).one()
        localinterest = self.localinterestmodel.query.filter_by(interest_id=interest.id).one()
        file = self.filesmodel(fileid=fid, filename=filename, interest=localinterest, mimetype=mimetype)
        db.session.add(file)
        db.session.commit()  # file is fully stored in the database now
                             # still needs to be stored physically in the filesystem at filepath

        return fid, filepath

class FilesCrud(DbCrudApiInterestsRolePermissions):
    def __init__(self, **kwargs):
        '''
        class for handling file management

        parameters added by this class:

        :param filesdirectory: function which returns main folder in which files are to be stored.
                Subdirectories are maintained by interest. Must be a function as this needs to be in app context
        '''
        if debug: current_app.logger.debug('FilesCrud.__init__()')

        # the args dict has default values for arguments added by this derived class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(
                    filesdirectory=None,
                    )
        args.update(kwargs)

        # this initialization needs to be done before checking any self.xxx attributes
        super().__init__(**args)

        # Caller must use local_interest_model
        if not callable(self.filesdirectory):
            raise ParameterError('filesdirectory required, and must be function')

    def deleterow(self, thisid):
        '''
        deletes row in Files, and deletes the file itself

        :param thisid: id of row to be deleted
        :return: []
        '''

        # determine the path of the file to delete. Note self.model = Files
        file = self.model.query.filter_by(id=thisid).one()
        fid = file.fileid
        # file's interest_id
        localinterest = self.local_interest_model.query.filter_by(id=file.interest_id).one()
        interest = Interest.query.filter_by(id=localinterest.interest_id).one()
        groupdir = join(self.filesdirectory(), interest.interest)
        filepath = join(groupdir, fid)

        # delete the Files record -- return what the super returns ([])
        row = super(FilesCrud, self).deleterow(thisid)

        # delete the file
        if exists(filepath):
            remove(filepath)

        return row

FILEID_LEN = 50
FILENAME_LEN = 256
MIMETYPE_LEN = 256  # hopefully overkill - see https://tools.ietf.org/html/rfc6838#section-4.2

class FilesMixin(object):
    fileid              = Column(String(FILEID_LEN))
    filename            = Column(String(FILENAME_LEN))
    mimetype            = Column(String(MIMETYPE_LEN))

