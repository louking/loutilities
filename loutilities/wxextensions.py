#!/usr/bin/python
###########################################################################################
#   wxextensions - extensions for wxPython widgets
#
#   Date        Author      Reason
#   ----        ------      ------
#   12/07/12    Lou King    Create
#   12/14/12    Lou King    Add deletecallback argument to AutoTextCtrl
#
#   Copyright 2012 Lou King
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
###########################################################################################
'''
wxextensions - extensions for wxPython widgets
========================================================
'''

# standard
import optparse

# pypi

# github

# other
import wx   # https://wxpython.org/pages/downloads/ - 2.9 minimum

# home grown

class InvalidParameter(Exception): pass

########################################################################
class AutoTextCtrl(wx.TextCtrl):
# some code copied from wxPython 2.9.4 demo for ListBox
########################################################################
    '''
    TextCtrl enhanced by associated list containing suggestions while typing

    :param *args: :class:`wx.TextCtrl` parameters
    :param **kwargs: :class:`wx.TextCtrl` keyword parameters
    :param items: list of initial items suggested while typing, default []
    :param delcallback: function to call when item deleted from items, default None - takes one parameter, text from deleted item
    '''
    #----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
    #----------------------------------------------------------------------
        '''
        remember items, instantiate TextCtrl using supplied parameters
        '''
        items = kwargs.pop('items', [])    # default for items is empty list
        if not isinstance(items, list):
            raise InvalidParameter('items must be list')
        self.setitems(items)
        
        self.setdelcallback(kwargs.pop('delcallback', None))
        
        self.typedText = ''
        self.itemndx = 0

        wx.TextCtrl.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_CHAR,self._OnKey)
        #self.Bind(wx.EVT_KEY_DOWN,self._OnKey)     # returns uppercase key
        
    #----------------------------------------------------------------------
    def setitems(self, items):
    #----------------------------------------------------------------------
        '''
        update the items used for autocompletion

        :param items: list of items suggested while typing
        '''
        self.items = items
        if '' not in self.items:
            self.items.append('')
        self.items.sort(cmp=lambda x,y: cmp(x.lower(), y.lower()))   # NOTE: '' ends up in 0 position
        
    #----------------------------------------------------------------------
    def setdelcallback(self, delcallback=None):
    #----------------------------------------------------------------------
        '''
        update the delcallback function, which is called when an item is deleted from items (list of suggested choices)

        :param delcallback: delcallback(item) is called when an item is deleted from items list.  None to disable
        '''
        self.delcallback = delcallback
        
    #----------------------------------------------------------------------
    def getitems(self):
    #----------------------------------------------------------------------
        '''
        return items used for autocompletion

        :rtype: list of items suggested while typing
        '''
        return self.items
    
    #----------------------------------------------------------------------
    def additem(self, item):
    #----------------------------------------------------------------------
        '''
        add an item to the list used for autocompletion

        :param item: item to add to list of items suggested while typing
        '''
        if item not in self.items:
            self.items.append(item)
            self.setitems(self.items)
        
    #----------------------------------------------------------------------
    def _FindPrefix(self, prefix):
    #----------------------------------------------------------------------
        '''
        find prefix as first substring of any item in self.items, ignoring case
        
        :param prefix: substring to look for
        '''

        if prefix:
            prefix = prefix.lower()
            length = len(prefix)

            # find first item which matches.  NOTE: self.items is a sorted list
            for i in range(len(self.items)):
                item = self.items[i]
                text = item.lower()

                if text[:length] == prefix:
                    # self.log.WriteText('Prefix %s is found.\n' % prefix)
                    return i

        # self.log.WriteText('Prefix %s is not found.\n' % prefix)
        return -1


    #----------------------------------------------------------------------
    def _OnKey(self, evt):
    #----------------------------------------------------------------------
        key = evt.GetKeyCode()

        # text gets added to typedText
        # search for typedText as initial part of item in self.items
        if key >= 32 and key < 127:     # 127 is DELETE key
            self.typedText = self.typedText + chr(key)
            self.itemndx = self._FindPrefix(self.typedText)
            self._SetSelection(self.itemndx)     # if prefix not found, self.typedText is selected

        # backspace removes one character and backs up
        elif key == wx.WXK_BACK:    
            self.typedText = self.typedText[:-1]

            if not self.typedText:
                self._SetSelection(0)   # 0 is always '' item
            else:
                self.itemndx = self._FindPrefix(self.typedText)
                self._SetSelection(self.itemndx)

        # down clears typedText and goes down an item in items
        elif key == wx.WXK_DOWN:    
            if self.itemndx != -1:
                self.typedText = ''
                self.itemndx +=1
                if self.itemndx >= len(self.items):
                    self.itemndx = 0
                self._SetSelection(self.itemndx)
            
            
        # up clears typedText and goes up an item in items
        elif key == wx.WXK_UP:
            if self.itemndx != -1:
                self.typedText = ''
                self.itemndx -=1
                if self.itemndx == -1:
                    self.itemndx = len(self.items)-1
                self._SetSelection(self.itemndx)
            
        # delete deletes selection (from end of typedText through end of found item)
        elif key == wx.WXK_DELETE:
            self.itemndx = -1
            self._SetSelection(self.itemndx)
            
        # ctrl-x deletes current item from list of items.  item is copied into TheClipboard
        elif key == wx.WXK_CONTROL_X:
            if self.itemndx > 0:        # and item in self.items needs to be in this AutoTextCtrl
                item = self.items.pop(self.itemndx)
                self.itemndx = 0
                self._SetSelection(self.itemndx)
                do = wx.TextDataObject()
                do.SetText(item)
                wx.TheClipboard.SetData(do)
                if self.delcallback:
                    self.delcallback(item)
                        
        # ctrl-v is a paste from TheClipboard
        # need to implement it here because TextCtrl hasn't put the data there yet
        elif key == wx.WXK_CONTROL_V:
            do = wx.TextDataObject()
            if wx.TheClipboard.GetData(do): # puts clipboard into do (yes, non-pythonic syntax)
                self.typedText += do.GetText()
            # else (no valid data in TheClipboard) leave self.typedText alone
            self.itemndx = self._FindPrefix(self.typedText)
            self._SetSelection(self.itemndx)
            
        else:
            self.typedText = ''
            evt.Skip()

    #----------------------------------------------------------------------
    def _SetSelection(self, itemndx):
    #----------------------------------------------------------------------
        '''
        set the value of the TextCtrl to the found item,
        select the portion of the item which was not yet typed
        
        :param itemndx: index into self.items
        '''

        # if typed text not found, just set the value
        if itemndx == -1:
            self.SetValue(self.typedText)
            self.SetInsertionPoint(len(self.typedText))
        else:
            self.SetValue(self.items[itemndx])      # NOTE: EVT_COMMAND_TEXT_UPDATED is generated
                                                    # use self.ChangeValue if that is not desired
            self.SetInsertionPoint(len(self.typedText))
            self.SetSelection(len(self.typedText),len(self.items[itemndx]))
        
########################################################################
class _TestWindow(wx.Frame):
########################################################################
    '''
    Test Window for widgets in this package

    :param parent: parent object for this form
    '''

    BTN_OK = wx.NewId()
    BTN_CNCL = wx.NewId()

    #----------------------------------------------------------------------
    def __init__(self,parent):
    #----------------------------------------------------------------------
        self.debug = False

        self.formname = 'test window'
        wx.Frame.__init__(self, parent, wx.ID_ANY, self.formname)
        self.Bind(wx.EVT_CLOSE, self.onClose)

        self.InitUI()
        self.Centre()
        self.Show()

    #----------------------------------------------------------------------
    def InitUI(self):
    #----------------------------------------------------------------------
        """
        Initialize the form
        """
        self.panel = wx.Panel(self)

        font = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT)
        font.SetPointSize(9)

        self.vbox = wx.BoxSizer(wx.VERTICAL)

        # hbox1 - text entry
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        st1 = wx.StaticText(self.panel, label='Enter Text')
        st1.SetFont(font)
        hbox1.Add(st1, proportion=1, flag=wx.RIGHT, border=8)
        self.tc = AutoTextCtrl(self.panel,style=wx.TE_PROCESS_ENTER,items=[
            '124 North Market St, Frederick, MD, USA',
            '748 SW Bay Blvd, Newport, OR, USA',
            '30 Germania St, Boston, MA, USA',
            ])
        self.Bind(wx.EVT_TEXT_ENTER, self.onEnter)
        hbox1.Add(self.tc, proportion=5, border=8)
        self.vbox.Add(hbox1, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)

        self.vbox.Add((-1, 10))

        self.panel.SetSizerAndFit(self.vbox)
        self.Fit()

    #----------------------------------------------------------------------
    def onEnter(self, evt):
    #----------------------------------------------------------------------
        """
        Search for address, then display rest of frame
        """
        print('text entered: {0}\n'.format(self.tc.GetValue()))
        self.tc.SetValue('')
        return

    #----------------------------------------------------------------------
    def onClose(self, evt):
    #----------------------------------------------------------------------
        """
        Just close the window without updating the station
        """
        self.tc.Destroy()
        self.Destroy()


#######################################################################
class _MyApp(wx.App):
########################################################################

    #----------------------------------------------------------------------
    def __init__(self):
    #----------------------------------------------------------------------
        """
        return MyApp object
        """
        wx.App.__init__(self, False)
        self.frame = _TestWindow(None)


################################################################################
def test():
################################################################################

    usage = "usage: %prog [options]\n"

    parser = optparse.OptionParser(usage=usage)
    (options, args) = parser.parse_args()

    # start the app
    app = _MyApp()
    app.MainLoop()

# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    test()

