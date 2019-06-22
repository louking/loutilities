function charts_get_focusid(container, i) {
    // assure unique focusid per chart
    let focusid = 'focus-' + i + '-';
    focusid += container.replace('#', '_');
    return focusid;
}

// line chart
class Chart {
    // options:
    //     data - [{'label':label, values: [{'x':number, 'value':value}, ... ]}, ... ]
    //     margin - 50 OR {top: 50, right: 50, bottom: 50, left: 50} (e.g.), default 40
    //     containerselect - e.g., 'body', '#divname', default 'body'
    //     xaxis - 'date', 'number', default 'number'
    //     xrange - array [startseq, endseq] seq are numeric, startseq may be higher then endseq
    //     xdirection - 'asc', 'desc', default 'asc'
    //     lastseq - optional sequence number to skip after, or {label:lastseq, ... } by label
    //     chartheader - optional text - if present, printed in the top center of the chart
    //     ytickincrement - y range is bumped up to next integral multiple of this value, default 100
    //     yaxislabel - optional text - if present, printed 90 deg rotated, on the left of the chart

    // extend config based on options
    constructor(options) {
        let that = this;
        that.options = {
            data: null,
            margin: 40,
            containerselect: 'body',
            chartheader: '',
            xaxis: 'number',
            xrange: [0, 100],
            xdirection: 'asc',
            lastseq: 0,
            yaxislabel: '',
            ytickincrement: 100,
        };
        that.options = Object.assign(that.options, options);

        // default show all labels
        that.showlabels = [];

        that.xascending = that.options.xdirection == 'asc';
        if (that.options.xaxis == 'number') {
            that.xscale = d3.scaleLinear;
            that.bisectX = d3.bisector(function (d, x) {
                if (that.xascending) {
                    return d.x - x;
                } else {
                    return x - d.x;
                }
            }).left;

            // incr is 1 when ascending, -1 when descending
            that.lowx = that.options.xrange[0];
            that.highx = that.options.xrange[1];
            that.incr = (that.xascending) ? 1 : -1;
            that.xrange = _.range(that.lowx, that.highx + that.incr, that.incr);
            that.tickformat = function(dx) { return dx };
            that.parsex = function(x) { return x; }
            that.atlastseq = function(lastseq, thisx) {
                return (lastseq > 0 && ((that.xascending && thisx >= lastseq) || (!that.xascending && thisx <= lastseq)))
            }

            that.focustext = function(d) {return d.x + " " + d.value}

        } else if (that.options.xaxis == 'date') {
            // see https://bl.ocks.org/gordlea/27370d1eea8464b04538e6d8ced39e89
            that.xscale = d3.scaleTime;
            // TODO: take xdirection option into account
            that.bisectX = d3.bisector(function(d) { return d.x; }).left;
            let parseDate = d3.timeParse("%m-%d");
            that.lowx = parseDate(that.options.xrange[0]);
            that.highx = parseDate(that.options.xrange[1]);
            that.xrange = [];
            for (let thisdate=new Date(that.lowx); thisdate<=that.highx; thisdate = new Date(thisdate.setDate(thisdate.getDate()+1))) {
                that.xrange.push(thisdate);
            }

            // see https://bl.ocks.org/d3noob/0e276dc70bb9184727ee47d6dd06e915
            that.tickformat = d3.timeFormat("%m/%d");

            that.parsex = function(x) {
                // translate date - maybe remove year first
                let datesplit = x.split('-');
                // check if year is present
                // TODO: needs to be special processing if previous year
                if (datesplit.length == 3) {
                    x = datesplit.slice(1).join('-');
                }
                return parseDate(x);
            }

            that.atlastseq = function(lastseq, thisx) {
                return (lastseq != '' && moment(thisx).format('MM-DD') >= lastseq)
            }

            let formatDate = d3.timeFormat("%m/%d");
            that.focustext = function(d) {return formatDate(d.x) + " " + d.value}

        } else {
            throw 'ERROR: unknown xaxis option value: ' + that.options.xaxis;
        }

        // convert margin if necessary
        if (typeof that.options.margin == 'number') {
            that.options.margin = {
                top: that.options.margin,
                right: that.options.margin,
                bottom: that.options.margin,
                left: that.options.margin
            };
        }
    }

    // draw the chart
    draw() {
        let that = this;

        // colors copied from matplotlib v2.0 - see https://matplotlib.org/users/dflt_style_changes.html#colors-in-default-property-cycle
        let colorcycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
            '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
            '#bcbd22', '#17becf'];
        let color = d3.scaleOrdinal()
            .range(['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
                '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
                '#bcbd22', '#17becf']);

        // get container
        let container = d3.select(that.options.containerselect),
            containerjs = document.querySelector(that.options.containerselect);

        // 2. Use the margin convention practice, for container
        let width = containerjs.clientWidth - that.options.margin.left - that.options.margin.right, // Use the container's width
            height = containerjs.clientHeight - that.options.margin.top - that.options.margin.bottom, // Use the container's height
            viewbox_width = width + that.options.margin.left + that.options.margin.right,
            viewbox_height = height + that.options.margin.top + that.options.margin.bottom;

        // 1. Add the SVG to the page and employ #2
        let svg = container.append("svg")
            .attr("width", width + that.options.margin.left + that.options.margin.right)
            .attr("height", height + that.options.margin.top + that.options.margin.bottom)
            .append("g")
            .attr("transform", "translate(" + that.options.margin.left + "," + that.options.margin.top + ")");

        // set up scales and ranges
        let x = this.xscale()
            .range([0, width]);
        let y = d3.scaleLinear()
            .range([height, 0]);

        // 5. X scale will use the x of our data
        x.domain([that.lowx, that.highx]);

        let xAxis = d3.axisBottom(x)
                .tickSize(16)
                .tickFormat(that.tickformat);

        let yAxis = d3.axisLeft(y);

        // ydomaindata is concatenation of all data for y.domain(d3.extent),
        // used to determine y domain
        let ydomaindata = [];
        for (i = 0; i < that.options.data.length; i++) {
            that.options.data[i].values.forEach(function (d) {
                d.x = that.parsex(d.x);
                // force number
                d.value = +d.value;
            });
            ydomaindata = ydomaindata.concat(that.options.data[i].values);
        }

        // seqdata is used to draw the paths so that there is a point for each number in the range
        let seqdata = [];
        for (let i = 0; i < that.options.data.length; i++) {
            let label = that.options.data[i].label;
            let checkvalues = _.cloneDeep(that.options.data[i].values);
            let seqvalues = [];
            let currvalue = 0;
            for (let j = 0; j < that.xrange.length; j++) {
                let thisx = that.xrange[j];
                while (checkvalues.length > 0
                       && ((that.xascending && checkvalues[0].x <= thisx)
                            || (!that.xascending && checkvalues[0].x >= thisx))) {
                    let thisitem = checkvalues.shift();
                    currvalue = thisitem.value;
                }
                seqvalues.push({x: thisx, value: currvalue});

                // break out after current sequence
                let lastseq;
                if (typeof that.options.lastseq != 'object') {
                    lastseq = that.options.lastseq;
                } else {
                    lastseq = that.options.lastseq[label];
                }
                if (that.atlastseq(lastseq, thisx)) {
                    break;
                }
            }
            seqdata.push({label: label, values: seqvalues});
        }


        // 6. Y scale will use the dataset values
        // force up to next boundary based on ytickincrement
        y.domain([0, Math.ceil(d3.max(ydomaindata, function (d) {
            return d.value
        }) / that.options.ytickincrement) * that.options.ytickincrement]);

        // 3. Call the x axis in a group tag
        svg.append("g")
            .attr("class", "x axis")
            .attr("transform", "translate(0," + height + ")")
            // see https://bl.ocks.org/d3noob/0e276dc70bb9184727ee47d6dd06e915
            .call(xAxis) // Create an axis component with d3.axisBottom
            // https://bl.ocks.org/d3noob/3c040800ff6457717cca586ae9547dbf
            .selectAll(".tick text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-65)");

        // 4. Call the y axis in a group tag
        svg.append("g")
            .attr("class", "y axis")
            .call(yAxis); // Create an axis component with d3.axisLeft

        // y axis text
        svg.append("text")
            .attr("transform", "rotate(-90)")
            // x and y are flipped due to the rotation. see https://leanpub.com/d3-t-and-t-v4/read#leanpub-auto-the-y-axis-label
            .attr("y", 0 - that.options.margin.left)
            .attr("x", 0 - (height / 2))
            .attr("dy", "1em")
            .style("text-anchor", "middle")
            .text(that.options.yaxislabel);

        // add heading if we have one
        svg.append("g")
            .attr("class", "heading")
            .append("text")
            .attr("transform", "translate(" + width / 2 + ",-10)")
            .style("text-anchor", "middle")
            .text(that.options.chartheader);

        // 7. d3's line generator
        let line = d3.line()
            .x(function (d) {
                return x(d.x); // set the x values for the line generator
            })
            .y(function (d) {
                return y(d.value); // set the y values for the line generator
            });
        // .curve(d3.curveMonotoneX) // apply smoothing to the line

        let colormap = [];
        for (let i = 0; i < seqdata.length; i++) {
            let label = seqdata[i].label;
            colormap.push({'label': label, 'color': colorcycle[i % colorcycle.length]});

            svg.append("path")
                .style("stroke", colormap[i].color)
                .datum(seqdata[i].values)
                .attr("class", "line alllabels label-"+label)
                .attr("d", line);

            // assure unique focusid per chart
            let thisfocus = svg.append("g")
                .attr("class", "focus focuslabel-"+label)
                .attr("id", charts_get_focusid(that.options.containerselect, i))
                .style("display", "none");

            thisfocus.append("circle")
                .attr("r", 4.5);

            thisfocus.append("text")
                .style("text-anchor", "start")
                .attr("x", 4)
                .attr("y", 7)
                .attr("dy", ".35em");
        }

        let legend = svg.selectAll(".legend")
            .data(colormap)
            .enter().append("g")
            .attr("class", function(d) {
                return 'legend alllabels label-'+d.label;
            })
            .attr("transform", function (d, i) {
                return "translate(" + i * 90 + ",0)";
            });

        legend.append("rect")
            .attr("y", height + that.options.margin.bottom - 15)
            .attr("x", 60)
            .attr("width", 15)
            .attr("height", 15)
            .style("fill", function (d) {
                return d.color
            });

        legend.append("text")
            .attr("x", 15)
            .attr("y", height + that.options.margin.bottom - 15)
            .attr("dy", ".8em")
            .style("text-anchor", "bottom")
            .text(function (d) {
                return d.label;
            });

        let mouseoverlay = svg.append("rect")
            .attr("class", "overlay")
            .attr("width", width + that.options.margin.right)
            .attr("height", height);

        let allfocus = d3.selectAll(".focus");
        mouseoverlay
            .on("mouseover", function () {
                // nothing in list means show all labels
                if (that.showlabels.length == 0) {
                    allfocus.style("display", null);

                // otherwise show just the labels in the list
                } else {
                    allfocus.style("display", "none");
                    for (let i=0; i<that.showlabels.length; i++) {
                        let label = that.showlabels[i];
                        d3.selectAll('.focuslabel-'+label).style("display", null);
                    }
                }
            })
            .on("mouseout", function () {
                allfocus.style("display", "none");
            })
            .on("mousemove", mousemove);

        function mousemove() {
            let x0 = x.invert(d3.mouse(this)[0]);
            for (let i = 0; i < seqdata.length; i++) {
                let j = that.bisectX(seqdata[i].values, x0);
                let d;
                // use d0, d1 if in range
                if (j < seqdata[i].values.length) {
                    let d0 = seqdata[i].values[j - 1],
                        d1 = seqdata[i].values[j];
                    d = x0 - d0.x > d1.x - x0 ? d1 : d0;
                } else {
                    d = seqdata[i].values[seqdata[i].values.length - 1]
                }
                let thisfocus = d3.select('#' + charts_get_focusid(that.options.containerselect, i));
                thisfocus.attr("transform", "translate(" + x(d.x) + "," + y(d.value) + ")");
                thisfocus.select("text").text(that.focustext(d));
                // console.log('d.x='+d.x+' d.value='+d.value+' x(d.x)='+x(d.x)+' y(d.value)='+y(d.value));
            }
        }
    }   // draw

    setshowlabels(labels) {
        let that = this;
        that.showlabels = labels;
        let alllabels = d3.selectAll(".alllabels");

        // nothing in list means show all labels
        if (that.showlabels.length == 0) {
            alllabels.style("display", null);

        // otherwise show just the labels in the list
        } else {
            alllabels.style("display", "none");
            for (let i=0; i<that.showlabels.length; i++) {
                let label = that.showlabels[i];
                d3.selectAll('.label-'+label).style("display", null);
            }
        }
    } // showlabels
}
