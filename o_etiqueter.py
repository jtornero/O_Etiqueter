# o_etiqueter
#
# This file is part of O_Etiqueter, an application for
# labelling vials for oceanographic rosette bottle samples.
#
# Copyright (C) 2020 Jorge Tornero @imasdemase, Ricardo Sánchez @ricardofsleal, Instituto Español de Oceanografía @IEOoceanografia
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from PyQt5 import QtCore, QtWidgets, QtGui
from configobj import ConfigObj
from datetime import datetime
import socket
import sys
from oetiqueter_ui import Ui_OEtiqueter as oetiketer_ui
from aboutdialog_ui import Ui_AboutDialog as aboutdialog_ui
    
class TableCellDelegate(QtWidgets.QStyledItemDelegate):
    
    # This is an item delegate for the table cells.
    # When the delegate is instantiated the combobox is filled with the values of
    # the lists depending on which column, instead of having a separate delegate for 
    # each column is of easier implementation, because the same delegate can be 
    # used for the wole table.
    
    # For a delegate to be reimplemented we need to override just some functions
    
    height = 25
    width = 200
    
    # List of preconfigured depths
    depths=['5 m', '25 m','50 m','75 m','100 m','125 m','200 m','300 m','400 m','500 m','600 m','700 m']
    #List of bottles
    bottles=['1', '2','3','4','5','6','7','8','9','10','11','12']
    # List of extra values, for instance DSL for Deep Scattering Layer or 
    # Bottom for the bottle closest to the bottom.
    extra=['','DSL   ','BOTTOM ','TURBID','INTERE']
    
    def createEditor(self, parent, option, index):
        
        # With the above on mind, we assign values to the comboboxes
        # depending on the table column index.
        
        editor = QtWidgets.QComboBox(parent)
        if index.column()==0:            
            self.editorItems=self.depths
            editor.setEditable(True)
        elif index.column()==1:
            self.editorItems=self.extra
            editor.setEditable(False)
        else:
            self.editorItems=self.bottles
            editor.setEditable(False)
            
        editor.addItems(self.editorItems)
        editor.setStyleSheet('QComboBox{font:20px;}')
        return editor
    
    def setEditorData(self,editor,index):
        
        editor.showPopup()
    
    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), QtCore.Qt.EditRole)
        model.setData(index, QtCore.Qt.AlignCenter, QtCore.Qt.TextAlignmentRole)
            

class Etiqueter(QtWidgets.QWidget):
    
    # Implementation of a widget for samples labelling
    # It has been implemented through a QWidget so it could
    # be easily integrated into other Qt applications.
    
    # This signal is emmited when the bottle configuration is OK. It means,
    # mainly, that the same bottle is not selected for different depths.
    bottlesOK = QtCore.pyqtSignal(bool)
    
    def __init__(self,configFile='./config.conf',**kwargs):
        
        super().__init__(**kwargs)    
        
        # Instantiation of the GUI
        self.ui=oetiketer_ui()
        self.ui.setupUi(self)
        
        
        
        # Loading of configuration file
        try:
            self.configuration=ConfigObj(configFile)
            
            self.variables=self.configuration['VARIABLES']
            self.varNames=self.variables.keys()
            
            self.stations=self.configuration['STATIONS']
            self.stnNames=['']
            self.stnNames+=(self.stations.keys())
            
            self.bottleDepths=self.configuration['DEPTHS']['depths']
            self.survey=self.configuration['SURVEY']['survey']        
            self.ui.surveyLabel.setText(self.survey)
            
            self.printerIp=self.configuration["PRINTER"]["IP"]
            self.printerPort=int(self.configuration["PRINTER"]["port"])
        
        except Exception as e:
            # In case something goes wrong with the configuration file, 
            # there is a warning an exits
            msg=QtWidgets.QMessageBox()
            msg.setWindowTitle('Missing/wrong configuration file')
            msg.setText('<center>There were problems reading the configuration file, please provide a valid configuration file and restart</center><br>%s' %e)
            msg.exec()
            exit()
        
        # Now we set the header of the table with the variable
        # names defined in the configuration file. But first two columns
        # are DEPTH and OBSERVATIONS
        
        self.columnLabels=['DEPTH','OBSERV.']
        
        
        for varName in self.varNames:
            self.columnLabels.append(varName)
        
        self.ui.tableWidget.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignCenter)
        
       
        self.ui.tableWidget.setColumnCount(len(self.varNames)+2)
        self.ui.tableWidget.setHorizontalHeaderLabels(self.columnLabels)
        
        # Here we set the tooltips for the columns
        self.ui.tableWidget.horizontalHeaderItem(0).setToolTip('Double click in a cell to edit depth or select from a list')
        self.ui.tableWidget.horizontalHeaderItem(1).setToolTip('Double click in a cell to select from a predefined observation list or edit')
        
        for column in range(2,len(self.varNames)+2):
            self.ui.tableWidget.horizontalHeaderItem(column).setToolTip('<b>Assign bottles by selecting cell(s)</b> and using the right buttons or function keys or                                                          <b>double-clicking</b> in a cell to select bottle from a list.')
        
        
        #We create the delegates and assing the delegates
        delPrf=TableCellDelegate(self.ui.tableWidget)
        self.ui.tableWidget.setItemDelegate(delPrf)
        self.ui.tableWidget.setStyleSheet('QTableWidget{font:20px;}')
        
        # Population of station values with station names
        self.ui.stationCombo.addItems(self.stnNames)
        
        # Print button is disabled by default, it will be enabled if
        # bottle/depth configuration is OK
        self.ui.printButton.setEnabled(False)
        self.bottlesOK.connect(self.enablePrintButton)
        
        # Signal/slots connectin
        self.ui.addDepthButton.clicked.connect(self.addRow2Table)
        self.ui.stationCombo.activated.connect(self.populateTable)
        self.ui.buttonGroup.buttonClicked.connect(self.assignBottle)
        self.ui.printButton.clicked.connect(self.printLabels)
        
        self.ui.tableWidget.selectionModel().selectionChanged.connect(self.checkSelection)
        self.ui.removeDepthButton.clicked.connect(self.removeRowFromTable)
        self.ui.tableWidget.currentCellChanged.connect(self.checkBottles)
        
        self.ui.aboutButton.clicked.connect(self.about)
        
        # And let's go!       
        self.show()
    
    def about(self):
        
        aboutDialog=QtWidgets.QDialog()
        aboutDialog.ui=aboutdialog_ui()
        aboutDialog.ui.setupUi(aboutDialog)
        aboutDialog.exec()
        
    
    def enablePrintButton(self,enable):
        # This function enables print button when the bottlesOK signal is
        # received, what means the bottle/depth configuration is OK
        self.ui.printButton.setEnabled(enable)
    
    def checkSelection(self,row,col):
        
        # This implements a not-across-columns cell selection for
        # QtableWidget, so it is not possible to select multiple cells in
        # the same column, thus preventing using the same bottle number for 
        # different depths
        
        selection=self.ui.tableWidget.selectedIndexes()
        
        rows={index.row() for index in selection}
        if len(rows)>1:
            self.ui.tableWidget.clearSelection()
    
    def checkBottles(self):
        
        # To check if bottles are assigned correctly,
        # we test if there are bottles assigned to more than
        # one depth.
        # First we check which bottles have been already assigned and
        # then check if they have more than one depth.
               
        columns=range(0,len(self.variables))
        rows=self.ui.tableWidget.rowCount()
        bottles=set()
        for column in columns:
            for row in range(0,rows+1):
                botIdx=self.ui.tableWidget.model().index(row,column+2)
                bottle=self.none2String(self.ui.tableWidget.model().data(botIdx))
                if bottle!='':
                    bottles.add(bottle)
        
        # We look for every item with that bottle selected and check in which
        # rows (depths) occurs. If it is more than one row, we highlight it in red,
        # otherwise in lightgreen
        # If any red cell occurs, print button is disabled.
        
                
        botOK=set() 
        for bottle in bottles:
            items=self.ui.tableWidget.findItems(bottle,QtCore.Qt.MatchExactly)
            rows={item.row() for item in items}
            print(bottle,rows)
            if len(rows)>1:
                brush=QtGui.QBrush(QtGui.QColor('red'))
                botOK.add(False)
            else:
                brush=QtGui.QBrush(QtGui.QColor('lightgreen'))
                botOK.add(True)
                
            for item in items:
                item.setBackground(brush)
            
            self.bottlesOK.emit(all(botOK))
    
    def none2String(self,string):
        
        # This is an auxiliary function that converts a None value in 
        # a string to just an empty string for checking purposes.
        
        if string is None:
            return ''
        else:
            return string
    
    def createLabel(self,survey,cast,station,bottle,depth,obs,variable):
        
        # This function creates the label itself.
        # The input parameter will we the same, however,
        # the string for the label could be changed for the code
        # to generate the label in a particular printer language.
        # In this case, the code provided is in Zebra ZPL-II language
        # for a ZEBRA 66680RM (1"x0.5", 38x13 mm) label.
        # Please notice that in this example both the logo, vessel name
        # and other anciallary fields are from Spanish Institute of
        # Oceanography, but you can create your own.
        # Please check Zebra's ZPL II programming guide available on 
        # the internet. Also, you can test your labels on Labelary Online
        # ZPL viewer at http://labelary.com/viewer.html
        
        # In the future, this could be implemented through a python plugin,
        # so labels could be not hard coded.
        
        # We get the date for the label from the system
        now = datetime.now()
        currentDate = now.strftime("%d/%m/%Y %H:%M")
        label="""
        ^XA
        ^CI28
        ^PW305
        ^FO4,11^GB175,30,20,B,1^FS
        ^FO5,15^FB175,1,0,L,0^AR,^FR^FD%s^FS    
        ^FO5,46^FB150,1,0,L,0^A0,10,10^FD29AJ Ángeles Alvariño^FS
		^FO5,59^FB90,1,0,L,0^AQ^FDCast:^FS        
        ^FO4,59^FB100,1,0,L,0^AQ^FDCast: %s^FS  
        ^FO182,16^FB83,1,0,L,0^AR^FR^FD%s^FS   
        ^FO115,59^FB90,1,0,L,0^AQ^FDBot:^FS        
        ^FO116,59^FB100,1,0,L,0^AQ^FDBot: %s^FS
        ^FO5,87^FB120,1,0,L,0^AQ^FDProf:^FS        
        ^FO6,87^FB120,1,0,L,0^AQ^FDProf: %s^FS
        ^FO123,87^FB70,1,0,L,0^AQ^FD%s^FS
        ^FO200,87^FB140,1,0,L,0^AR,^FD%s^FS
        ^FO196,83^GB100,30,1,b,1^FS   
        ^FO198,52^FB70,2,0,C,0^AA^FD%s^FS
        ^FO257,47^FB50,2,0,C,0^AP^FDIEO Cádiz^FS
        ^FO270,9^GFA,120,120,4,,:003FF,00IFC,03IFE,07JF8,0FF07FC,1FC00FC,1F8307E,3F1863F,3E2091F,3C4108F,1C8104F80C8104780C80843800IFC3805IFC380CIFC781CIFCF83CIFCF,3E7FF9F,3F3FF3F,1F0FC7E,1FC00FE,0FF03FC,07JF8,03JF,01IFC,007FF,I078,^FS            
        ^XZ
         """ %(survey,cast,station,bottle,depth,obs,variable,currentDate)
        return label
    
    def printLabels(self):
        
        # To print the labels we gather all label information
        # and generate each of the labels into a list which
        # is later joined into one string which is finally
        # sent to the printer.
        # Right now just printing through ethernet is supported,
        # however, printing throug usb/serial will be implemented.
        

        survey=self.survey
        cast=self.ui.castText.text()
        station=self.ui.stationCombo.currentText()
        
        labelList=[]
        
        columns=range(0,len(self.variables))
        rows=self.ui.tableWidget.rowCount()
        for columna in columns:
            
            varName=self.varNames[columna]
            replicas=self.variables.as_int(varName)
            for fila in range(0,rows+1):
                # We get the index for depth, observations and index
                depthIdx=self.ui.tableWidget.model().index(fila,0)
                obsIdx=self.ui.tableWidget.model().index(fila,1)
                botIdx=self.ui.tableWidget.model().index(fila,columna+2)
                
                depth=self.ui.tableWidget.model().data(depthIdx)
                obs=self.none2String(self.ui.tableWidget.model().data(obsIdx))
                bottle=self.none2String(self.ui.tableWidget.model().data(botIdx))
                if botle!='': # Only print cells with assigned bottle
                    if replicas>1:
                        for replica in range(replicas):
                            shortVarName=varName.upper()[:4]
                            variable='%s/%s' %(shortVarName,replica+1)
                            label=self.createLabel(survey,cast,station,bottle,detph,obs,variable)
                            labelList.append(label)
                    else:
                        shortVarName=varName.upper()[:6]
                        label=self.createLabel(survey,cast,station,bottle,depth,obs,shortVarName)
                        labelList.append(label)
                                
        # We must reverse the order of labelList for the labels to be printed in the correct order
        labels='\n'.join(reversed(labelList))
        
        # Creation of the socket with the parameters got from the configuration file
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.printerIp, self.printerPort))
        sock.send(labels.encode('utf-8'))
        sock.close()
    
    def populateTable(self):
        
        #Population of table contents
        self.ui.tableWidget.setRowCount(0)
        defaultProfs=[int(p) for p in self.bottleDepths]
        stn=self.ui.stationCombo.currentText()
        if stn!='':
            stnMaxProf=int(self.stations[stn])
            depths=[p for p in defaultProfs  if p<stnMaxProf]
            for p in depths:
                self.addRow2Table('%i m' %p)
    
    def assignBottle(self,bottleButton):
        
        # This function makes possible to assign bottles
        # with the right panel buttons.
        # The current implementation is for 12 bottles rosette
        
        bottleNumber=bottleButton.text()
        if bottleNumber=='NO':
            bottleNumber=''
        print (bottleNumber)
        selection=self.ui.tableWidget.selectedIndexes()
        for index in selection:
            col=index.column()
            row=index.row()
            if col>1: # Preventing depth and obs of being modified
                self.ui.tableWidget.takeItem(row,col)
                item=QtWidgets.QTableWidgetItem(bottleNumber)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.ui.tableWidget.setItem(row,col,item)
        
        self.checkBottles()
        
    def addRow2Table(self,prof=None):
        
        # Adding a row in the table for another depth
        
        newRow=self.ui.tableWidget.rowCount()
        self.ui.tableWidget.insertRow(newRow)
        if prof is None:
            item=QtWidgets.QTableWidgetItem('')
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.ui.tableWidget.setItem(newRow,0,item)
        else:
            item=QtWidgets.QTableWidgetItem(prof)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.ui.tableWidget.setItem(newRow,0,item)
            
    def removeRowFromTable(self,prof=None):
        
        # Removind a row in the table
        self.ui.tableWidget.removeRow(self.ui.tableWidget.currentRow())
       
    
        
    
# Application starts

app=QtWidgets.QApplication(sys.argv)
etiqueter=Etiqueter()
sys.exit(app.exec())
