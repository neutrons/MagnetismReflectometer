echo "**********************************************"
echo "* POINT YOUR BROWSER TO http://127.0.0.1:5000/"
echo "**********************************************"
exec gunicorn --timeout 60 --bind :5000 reduce_REF_M_run:app
